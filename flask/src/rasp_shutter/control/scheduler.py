#!/usr/bin/env python3
import datetime
import enum
import logging
import re
import threading
import time
import traceback
from typing import Any

import my_lib.footprint
import my_lib.serializer
import my_lib.time
import my_lib.webapp.config
import my_lib.webapp.log
import rasp_shutter.config
import rasp_shutter.control.config
import rasp_shutter.control.webapi.control
import rasp_shutter.control.webapi.sensor
import rasp_shutter.types
import rasp_shutter.util
import schedule


class BRIGHTNESS_STATE(enum.IntEnum):
    DARK = 0
    BRIGHT = 1
    UNKNOWN = 2


RETRY_COUNT = 3

# schedule ライブラリの曜日メソッド名（日曜始まり、wday[0]=日曜 に対応）
WEEKDAY_METHODS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

# 時刻フォーマット検証用パターン（HH:MM形式）
SCHEDULE_TIME_PATTERN = re.compile(r"\d{2}:\d{2}")

should_terminate = threading.Event()

# Worker-specific instances for pytest-xdist parallel execution
_scheduler_instances: dict[str, schedule.Scheduler] = {}
_schedule_data_instances: dict[str, rasp_shutter.types.ScheduleData | None] = {}
_schedule_lock_instances: dict[str, threading.Lock] = {}
_auto_control_events: dict[str, threading.Event] = {}


def get_scheduler() -> schedule.Scheduler:
    """Get worker-specific scheduler instance for pytest-xdist parallel execution"""
    worker_id = rasp_shutter.util.get_worker_id()

    if worker_id not in _scheduler_instances:
        # Create a new scheduler instance for this worker
        _scheduler_instances[worker_id] = schedule.Scheduler()

    return _scheduler_instances[worker_id]


def get_schedule_lock() -> threading.Lock:
    """Get worker-specific schedule lock for pytest-xdist parallel execution"""
    worker_id = rasp_shutter.util.get_worker_id()

    if worker_id not in _schedule_lock_instances:
        _schedule_lock_instances[worker_id] = threading.Lock()

    return _schedule_lock_instances[worker_id]


def get_auto_control_event():
    """テスト同期用のワーカー固有自動制御イベントを取得"""
    worker_id = rasp_shutter.util.get_worker_id()

    if worker_id not in _auto_control_events:
        _auto_control_events[worker_id] = threading.Event()

    return _auto_control_events[worker_id]


def _signal_auto_control_completed():
    """自動制御サイクルの完了をシグナル（テスト用）"""
    # テスト環境でのみイベントを設定
    if rasp_shutter.util.is_pytest_running():
        event = get_auto_control_event()
        event.set()


def wait_for_auto_control_completion(timeout=5.0):
    """自動制御の完了を待機（テスト用）"""
    if not rasp_shutter.util.is_pytest_running():
        return True

    event = get_auto_control_event()
    event.clear()  # 待機前にクリア
    return event.wait(timeout)


def get_schedule_data() -> rasp_shutter.types.ScheduleData | None:
    """Get worker-specific schedule data for pytest-xdist parallel execution"""
    worker_id = rasp_shutter.util.get_worker_id()

    if worker_id not in _schedule_data_instances:
        _schedule_data_instances[worker_id] = None

    return _schedule_data_instances[worker_id]


def set_schedule_data(data: rasp_shutter.types.ScheduleData | dict[str, Any] | None) -> None:
    """Set worker-specific schedule data for pytest-xdist parallel execution"""
    worker_id = rasp_shutter.util.get_worker_id()
    _schedule_data_instances[worker_id] = data  # type: ignore[assignment]


def init() -> None:
    global should_terminate

    # ワーカー固有のロックを初期化
    get_schedule_lock()
    should_terminate.clear()


def term():
    global should_terminate

    should_terminate.set()


def brightness_text(
    sense_data: rasp_shutter.types.SensorData,
    cur_schedule_data: rasp_shutter.types.ScheduleEntry | dict[str, Any],
) -> str:
    # TypedDictへの動的アクセスを避けるため、dictに展開
    schedule_dict: dict[str, Any] = {**cur_schedule_data}

    def sensor_text(sensor: str) -> str:
        sensor_value = getattr(sense_data, sensor)
        current = sensor_value.value
        threshold = schedule_dict[sensor]
        if current > threshold:
            cmp = ">"
        elif current < threshold:
            cmp = "<"
        else:
            cmp = "="
        return f"{sensor}: current {current:.1f} {cmp} threshold {threshold:.1f}"

    text = [sensor_text(sensor) for sensor in ["solar_rad", "lux", "altitude"]]

    return ", ".join(text)


def check_brightness(sense_data: rasp_shutter.types.SensorData, action: str) -> BRIGHTNESS_STATE:
    if not sense_data.lux.valid or not sense_data.solar_rad.valid:
        return BRIGHTNESS_STATE.UNKNOWN

    schedule_data = get_schedule_data()
    assert schedule_data is not None, "Schedule data not initialized"  # noqa: S101

    # validがTrueの場合、valueはNoneではない
    lux_value = sense_data.lux.value
    solar_rad_value = sense_data.solar_rad.value
    altitude_value = sense_data.altitude.value
    assert lux_value is not None and solar_rad_value is not None  # noqa: S101
    assert altitude_value is not None  # noqa: S101

    if action == "close":
        close_data = schedule_data["close"]
        if (
            lux_value < close_data["lux"]
            or solar_rad_value < close_data["solar_rad"]
            or altitude_value < close_data["altitude"]
        ):
            logging.info("Getting darker %s", brightness_text(sense_data, close_data))
            return BRIGHTNESS_STATE.DARK
        else:
            return BRIGHTNESS_STATE.BRIGHT
    else:
        open_data = schedule_data["open"]
        if (
            lux_value > open_data["lux"]
            and solar_rad_value > open_data["solar_rad"]
            and altitude_value > open_data["altitude"]
        ):
            logging.info("Getting brighter %s", brightness_text(sense_data, open_data))
            return BRIGHTNESS_STATE.BRIGHT
        else:
            return BRIGHTNESS_STATE.DARK


def exec_shutter_control_impl(
    config: rasp_shutter.config.AppConfig,
    state: str,
    mode: rasp_shutter.control.webapi.control.CONTROL_MODE,
    sense_data: rasp_shutter.types.SensorData,
    user: str,
) -> bool:
    try:
        # NOTE: Web 経由だと認証つけた場合に困るので、直接関数を呼ぶ
        rasp_shutter.control.webapi.control.set_shutter_state(
            config, list(range(len(config.shutter))), state, mode, sense_data, user
        )
        return True
    except Exception:
        logging.exception("Failed to control shutter")

    return False


def exec_shutter_control(
    config: rasp_shutter.config.AppConfig,
    state: str,
    mode: rasp_shutter.control.webapi.control.CONTROL_MODE,
    sense_data: rasp_shutter.types.SensorData,
    user: str,
) -> bool:
    logging.debug("Execute shutter control")

    for _ in range(RETRY_COUNT):
        if exec_shutter_control_impl(config, state, mode, sense_data, user):
            return True
        logging.debug("Retry")

    my_lib.webapp.log.info("😵 シャッターの制御に失敗しました。")
    return False


def shutter_auto_open(config: rasp_shutter.config.AppConfig) -> None:
    logging.debug("try auto open")

    schedule_data = get_schedule_data()
    assert schedule_data is not None, "Schedule data not initialized"  # noqa: S101
    if not schedule_data["open"]["is_active"]:
        logging.debug("inactive")
        return

    elapsed_pending_open = my_lib.footprint.elapsed(rasp_shutter.control.config.STAT_PENDING_OPEN)
    if elapsed_pending_open > rasp_shutter.control.config.ELAPSED_PENDING_OPEN_MAX_SEC:
        # NOTE: 暗くて開けるのを延期されている場合以外は処理を行わない。
        logging.debug("NOT pending")
        return

    elapsed_auto_close = my_lib.footprint.elapsed(rasp_shutter.control.config.STAT_AUTO_CLOSE)
    if elapsed_auto_close < rasp_shutter.control.config.EXEC_INTERVAL_AUTO_MIN * 60:
        # NOTE: 自動で閉めてから時間が経っていない場合は、処理を行わない。
        logging.debug("just closed before %d", elapsed_auto_close)
        return

    sense_data = rasp_shutter.control.webapi.sensor.get_sensor_data(config)
    if check_brightness(sense_data, "open") == BRIGHTNESS_STATE.BRIGHT:
        sensor_text = rasp_shutter.control.webapi.control.sensor_text(sense_data)
        my_lib.webapp.log.info(f"📝 暗くて延期されていましたが、明るくなってきたので開けます。{sensor_text}")

        exec_shutter_control(
            config,
            "open",
            rasp_shutter.control.webapi.control.CONTROL_MODE.AUTO,
            sense_data,
            "sensor",
        )
        my_lib.footprint.clear(rasp_shutter.control.config.STAT_PENDING_OPEN)
        my_lib.footprint.clear(rasp_shutter.control.config.STAT_AUTO_CLOSE)
    else:
        logging.debug(
            "Skip pendding open (solar_rad: %.1f W/m^2, lux: %.1f LUX)",
            sense_data.solar_rad.value if sense_data.solar_rad.valid else -1,
            sense_data.lux.value if sense_data.lux.valid else -1,
        )


def conv_schedule_time_to_datetime(schedule_time: str) -> datetime.datetime:
    now = my_lib.time.now()
    time_obj = datetime.datetime.strptime(schedule_time, "%H:%M").time()
    return datetime.datetime.combine(now.date(), time_obj, tzinfo=my_lib.time.get_zoneinfo())


def shutter_auto_close(config: rasp_shutter.config.AppConfig) -> None:
    logging.debug("try auto close")

    schedule_data = get_schedule_data()
    assert schedule_data is not None, "Schedule data not initialized"  # noqa: S101
    if not schedule_data["close"]["is_active"]:
        logging.debug("inactive")
        return
    elif abs(
        my_lib.time.now() - conv_schedule_time_to_datetime(schedule_data["open"]["time"])
    ) < datetime.timedelta(minutes=1):
        # NOTE: 開ける時刻付近の場合は処理しない
        logging.debug("near open time")
        return
    elif (
        my_lib.time.now() <= conv_schedule_time_to_datetime(schedule_data["open"]["time"])
    ) or my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_OPEN):
        # NOTE: 開ける時刻よりも早い場合は処理しない
        logging.debug("before open time")
        return
    elif conv_schedule_time_to_datetime(schedule_data["close"]["time"]) <= my_lib.time.now():
        # NOTE: スケジュールで閉めていた場合は処理しない
        logging.debug("after close time")
        return
    elif (
        my_lib.footprint.elapsed(rasp_shutter.control.config.STAT_AUTO_CLOSE)
        <= rasp_shutter.control.config.ELAPSED_AUTO_CLOSE_MAX_SEC
    ):
        # NOTE: 12時間以内に自動で閉めていた場合は処理しない
        logging.debug("already close")
        return

    for index in range(len(config.shutter)):
        elapsed_open = my_lib.footprint.elapsed(
            rasp_shutter.control.webapi.control.exec_stat_file("open", index)
        )
        if elapsed_open < rasp_shutter.control.config.EXEC_INTERVAL_AUTO_MIN * 60:
            # NOTE: 自動で開けてから時間が経っていない場合は、処理を行わない。
            logging.debug("just opened before %d sec (%d)", elapsed_open, index)
            return

    sense_data = rasp_shutter.control.webapi.sensor.get_sensor_data(config)
    if check_brightness(sense_data, "close") == BRIGHTNESS_STATE.DARK:
        sensor_text = rasp_shutter.control.webapi.control.sensor_text(sense_data)
        my_lib.webapp.log.info(
            f"📝 予定より早いですが、暗くなってきたので閉めます。{sensor_text}",
        )

        exec_shutter_control(
            config,
            "close",
            rasp_shutter.control.webapi.control.CONTROL_MODE.AUTO,
            sense_data,
            "sensor",
        )
        logging.info("Set Auto CLOSE")
        my_lib.footprint.update(rasp_shutter.control.config.STAT_AUTO_CLOSE)

        # NOTE: まだ明るくなる可能性がある時間帯の場合、再度自動的に開けるようにする
        hour = my_lib.time.now().hour
        if (
            hour > rasp_shutter.control.config.HOUR_MORNING_START
            and hour < rasp_shutter.control.config.HOUR_PENDING_OPEN_END
        ):
            logging.info("Set Pending OPEN")
            my_lib.footprint.update(rasp_shutter.control.config.STAT_PENDING_OPEN)

    else:  # pragma: no cover
        # NOTE: pending close の制御は無いのでここには来ない。
        logging.debug(
            "Skip pendding close (solar_rad: %.1f W/m^2, lux: %.1f LUX)",
            sense_data.solar_rad.value if sense_data.solar_rad.valid else -1,
            sense_data.lux.value if sense_data.lux.valid else -1,
        )


def shutter_auto_control(config: rasp_shutter.config.AppConfig) -> None:
    hour = my_lib.time.now().hour
    cfg = rasp_shutter.control.config

    # NOTE: 時間帯によって自動制御の内容を分ける
    if hour > cfg.HOUR_MORNING_START and hour < cfg.HOUR_AUTO_OPEN_END:
        shutter_auto_open(config)

    if hour > cfg.HOUR_MORNING_START and hour < cfg.HOUR_AUTO_CLOSE_END:
        shutter_auto_close(config)

    # テスト同期用の完了シグナル
    _signal_auto_control_completed()


def shutter_schedule_control(config: rasp_shutter.config.AppConfig, state: str) -> None:
    logging.info("Execute schedule control")

    sense_data = rasp_shutter.control.webapi.sensor.get_sensor_data(config)

    if check_brightness(sense_data, state) == BRIGHTNESS_STATE.UNKNOWN:
        error_sensor = []

        if not sense_data.solar_rad.valid:
            error_sensor.append("日射センサ")
        if not sense_data.lux.valid:
            error_sensor.append("照度センサ")

        error_sensor_text = "と".join(error_sensor)
        state_text = rasp_shutter.types.state_to_action_text(state)
        my_lib.webapp.log.error(f"😵 {error_sensor_text}の値が不明なので{state_text}るのを見合わせました。")
        _signal_auto_control_completed()
        return

    if state == "open":
        if check_brightness(sense_data, state) == BRIGHTNESS_STATE.DARK:
            sensor_text = rasp_shutter.control.webapi.control.sensor_text(sense_data)
            my_lib.webapp.log.info(f"📝 まだ暗いので開けるのを見合わせました。{sensor_text}")

            rasp_shutter.control.webapi.control.cmd_hist_push(
                {
                    "cmd": "pending",
                    "state": state,
                }
            )

            # NOTE: 暗いので開けれなかったことを通知
            logging.info("Set Pending OPEN")
            my_lib.footprint.update(rasp_shutter.control.config.STAT_PENDING_OPEN)
        else:
            # NOTE: ここにきたときのみ、スケジュールに従って開ける
            exec_shutter_control(
                config,
                state,
                rasp_shutter.control.webapi.control.CONTROL_MODE.SCHEDULE,
                sense_data,
                "scheduler",
            )
    else:
        my_lib.footprint.clear(rasp_shutter.control.config.STAT_PENDING_OPEN)
        exec_shutter_control(
            config,
            state,
            rasp_shutter.control.webapi.control.CONTROL_MODE.SCHEDULE,
            sense_data,
            "scheduler",
        )

    # テスト同期用の完了シグナル
    _signal_auto_control_completed()


SCHEDULE_FIELD_TYPES: dict[str, type] = {
    "is_active": bool,
    "lux": int,
    "altitude": int,
    "solar_rad": int,
}


def schedule_validate(schedule_data: dict) -> bool:
    if len(schedule_data) != 2:
        logging.warning("Count of entry is Invalid: %d", len(schedule_data))
        return False

    for entry in schedule_data.values():
        for key in ["is_active", "time", "wday", "solar_rad", "lux", "altitude"]:
            if key not in entry:
                logging.warning("Does not contain %s", key)
                return False

        # 辞書ベースのループで型チェック
        for field, expected_type in SCHEDULE_FIELD_TYPES.items():
            if not isinstance(entry.get(field), expected_type):
                logging.warning("Type of %s is invalid: %s", field, type(entry.get(field)))
                return False

        if not SCHEDULE_TIME_PATTERN.search(entry["time"]):
            logging.warning("Format of time is invalid: %s", entry["time"])
            return False
        if len(entry["wday"]) != 7:
            logging.warning("Count of wday is Invalid: %d", len(entry["wday"]))
            return False
        for i, wday_flag in enumerate(entry["wday"]):
            if not isinstance(wday_flag, bool):
                logging.warning("Type of wday[%d] is Invalid: %s", i, type(entry["wday"][i]))
                return False
    return True


def schedule_store(schedule_data: dict) -> None:
    schedule_path = my_lib.webapp.config.SCHEDULE_FILE_PATH
    assert schedule_path is not None, "SCHEDULE_FILE_PATH not configured"  # noqa: S101

    try:
        with get_schedule_lock():
            my_lib.serializer.store(schedule_path, schedule_data)
    except Exception:
        logging.exception("Failed to save schedule settings.")
        my_lib.webapp.log.error("😵 スケジュール設定の保存に失敗しました。")


def gen_schedule_default():
    _cfg = rasp_shutter.control.config
    schedule_data = {
        "is_active": False,
        "time": "00:00",
        "solar_rad": 0,
        "lux": 0,
        "altitude": 0,
        "wday": [True] * 7,
    }

    return {
        "open": schedule_data
        | {
            "time": _cfg.DEFAULT_OPEN_TIME,
            "solar_rad": _cfg.DEFAULT_OPEN_SOLAR_RAD,
            "lux": _cfg.DEFAULT_OPEN_LUX,
        },
        "close": schedule_data
        | {
            "time": _cfg.DEFAULT_CLOSE_TIME,
            "solar_rad": _cfg.DEFAULT_CLOSE_SOLAR_RAD,
            "lux": _cfg.DEFAULT_CLOSE_LUX,
        },
    }


def schedule_load() -> dict:
    schedule_default = gen_schedule_default()
    schedule_path = my_lib.webapp.config.SCHEDULE_FILE_PATH
    assert schedule_path is not None, "SCHEDULE_FILE_PATH not configured"  # noqa: S101

    try:
        with get_schedule_lock():
            schedule_data = my_lib.serializer.load(schedule_path, schedule_default)
            if schedule_validate(schedule_data):
                return schedule_data
    except Exception:
        logging.exception("Failed to load schedule settings.")
        my_lib.webapp.log.error("😵 スケジュール設定の読み出しに失敗しました。")

    return schedule_default


def set_schedule(config: rasp_shutter.config.AppConfig, schedule_data: dict) -> None:
    scheduler = get_scheduler()
    scheduler.clear()

    for state, entry in schedule_data.items():
        if not entry["is_active"]:
            continue

        for i, wday_method_name in enumerate(WEEKDAY_METHODS):
            if entry["wday"][i]:
                wday_method = getattr(scheduler.every(), wday_method_name)
                wday_method.at(entry["time"], my_lib.time.get_pytz()).do(
                    shutter_schedule_control, config, state
                )

    for job in scheduler.get_jobs():
        logging.info("Next run: %s", job.next_run)

    idle_sec = scheduler.idle_seconds
    if idle_sec is not None:
        hours, remainder = divmod(idle_sec, 3600)
        minutes, seconds = divmod(remainder, 60)

        logging.info(
            "Now is %s, time to next jobs is %d hour(s) %d minute(s) %d second(s)",
            my_lib.time.now().strftime("%Y-%m-%d %H:%M"),
            hours,
            minutes,
            seconds,
        )

    scheduler.every(1).seconds.do(shutter_auto_control, config)


def schedule_worker(config: rasp_shutter.config.AppConfig, queue) -> None:
    global should_terminate

    sleep_sec = 0.5
    scheduler = get_scheduler()

    liveness_file = config.liveness.file.scheduler

    logging.info("Load schedule")
    schedule_data = schedule_load()
    set_schedule_data(schedule_data)

    set_schedule(config, schedule_data)

    logging.info("Start schedule worker")

    i = 0
    while True:
        if should_terminate.is_set():
            scheduler.clear()
            break

        try:
            if not queue.empty():
                schedule_data = queue.get()
                set_schedule_data(schedule_data)
                set_schedule(config, schedule_data)
                schedule_store(schedule_data)

            idle_sec = scheduler.idle_seconds
            if idle_sec is not None:
                hours, remainder = divmod(idle_sec, 3600)
                minutes, seconds = divmod(remainder, 60)

            scheduler.run_pending()

            logging.debug("Sleep %.1f sec...", sleep_sec)
            time.sleep(sleep_sec)
        except OverflowError:  # pragma: no cover
            # NOTE: テストする際、freezer 使って日付をいじるとこの例外が発生する
            logging.debug(traceback.format_exc())

        if i % (10 / sleep_sec) == 0:
            my_lib.footprint.update(liveness_file)

        i += 1

    logging.info("Terminate schedule worker")


if __name__ == "__main__":
    import multiprocessing
    import multiprocessing.pool

    import my_lib.config
    import my_lib.logger

    my_lib.logger.init("test", level=logging.DEBUG)

    def test_func():
        logging.info("TEST")

        should_terminate.set()

    config = my_lib.config.load()
    queue = multiprocessing.Queue()

    init()

    pool = multiprocessing.pool.ThreadPool(processes=1)
    result = pool.apply_async(schedule_worker, (config, queue))

    exec_time = my_lib.time.now() + datetime.timedelta(seconds=5)
    queue.put(
        {
            "open": {
                "time": exec_time.strftime("%H:%M"),
                "is_active": True,
                "wday": [True] * 7,
                "solar_rad": 0,
                "lux": 0,
                "altitude": 0,
                "func": test_func,
            }
        }
    )

    # NOTE: 終了するのを待つ
    result.get()
