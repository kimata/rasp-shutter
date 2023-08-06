#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging
import pathlib
import pickle
import re
import threading
import time
import traceback
from enum import IntEnum

import rasp_shutter_control
import rasp_shutter_sensor
import schedule
from webapp_config import SCHEDULE_DATA_PATH, STAT_AUTO_CLOSE, STAT_PENDING_OPEN, TIMEZONE
from webapp_log import APP_LOG_LEVEL, app_log


class BRIGHTNESS_STATE(IntEnum):
    DARK = 0
    BRIGHT = 1
    UNKNOWN = 2


RETRY_COUNT = 3

schedule_lock = None
schedule_data = None
should_terminate = False


def init():
    global schedule_lock
    schedule_lock = threading.Lock()

    STAT_PENDING_OPEN.parent.mkdir(parents=True, exist_ok=True)
    STAT_AUTO_CLOSE.parent.mkdir(parents=True, exist_ok=True)


# NOTE: feeezer でテストしやすくするため，ファイルの mtime ではなく，
# epoch time を書き込んでそれを使う．
def exec_check_update(check_file):
    with open(check_file, mode="w") as f:
        f.write(str(time.time()))


def exec_check_elapsed_time(check_file):
    diff_sec = time.time()
    if not check_file.exists():
        return diff_sec

    if check_file.exists():
        with open(check_file) as f:
            diff_sec -= float(f.read())

    return diff_sec


def brightness_text(sense_data, cur_schedule_data):
    text = []
    for sensor in ["solar_rad", "lux"]:
        text.append(
            "{sensor}: current {current:.1f} {cmp} threshold {threshold:.1f}".format(
                sensor=sensor,
                current=sense_data[sensor]["value"],
                threshold=cur_schedule_data[sensor],
                cmp=">"
                if sense_data[sensor]["value"] > cur_schedule_data[sensor]
                else ("<" if sense_data[sensor]["value"] < cur_schedule_data[sensor] else "="),
            )
        )

    return ", ".join(text)


def check_brightness(sense_data, state):
    if (not sense_data["lux"]["valid"]) or (not sense_data["solar_rad"]["valid"]):
        return BRIGHTNESS_STATE.UNKNOWN

    if (sense_data["lux"]["value"] < schedule_data[state]["lux"]) and (
        sense_data["solar_rad"]["value"] < schedule_data[state]["solar_rad"]
    ):
        if state == "close":
            logging.info(
                "Getting darker {brightness_text}.".format(
                    brightness_text=brightness_text(sense_data, schedule_data[state])
                ),
            )
        return BRIGHTNESS_STATE.DARK
    else:
        if state == "open":
            logging.info(
                "Getting brighter {brightness_text}.".format(
                    brightness_text=brightness_text(sense_data, schedule_data[state])
                ),
            )
        return BRIGHTNESS_STATE.BRIGHT


def exec_shutter_control_impl(config, state, mode, sense_data, user):
    try:
        # NOTE: Web 経由だと認証つけた場合に困るので，直接関数を呼ぶ
        rasp_shutter_control.set_shutter_state(
            config, list(range(len(config["shutter"]))), state, mode, sense_data, user
        )
        return True
    except Exception as e:
        logging.warning(e)
        logging.warning(traceback.format_exc())
        pass

    return False


def exec_shutter_control(config, state, mode, sense_data, user):
    logging.debug("Execute shutter control")

    for i in range(RETRY_COUNT):
        if exec_shutter_control_impl(config, state, mode, sense_data, user):
            return True

    app_log("😵 シャッターの制御に失敗しました。")
    return False


def shutter_auto_open(config):
    if not schedule_data["open"]["is_active"]:
        return

    if exec_check_elapsed_time(STAT_PENDING_OPEN) > 6 * 60 * 60:
        # NOTE: 暗くて開けるのを延期されている場合以外は処理を行わない．
        return

    if exec_check_elapsed_time(STAT_AUTO_CLOSE) < 10 * 60:
        # NOTE: 自動で閉めてから時間が経っていない場合は，処理を行わない．
        return

    sense_data = rasp_shutter_sensor.get_sensor_data(config)
    if check_brightness(sense_data, "open") == BRIGHTNESS_STATE.BRIGHT:
        app_log(
            ("📝 暗くて延期されていましたが，明るくなってきたので開けます．{sensor_text}").format(
                sensor_text=rasp_shutter_control.sensor_text(sense_data),
            )
        )

        exec_shutter_control(config, "open", rasp_shutter_control.CONTROL_MODE.AUTO, sense_data, "sensor")
        STAT_PENDING_OPEN.unlink(missing_ok=True)
        STAT_AUTO_CLOSE.unlink(missing_ok=True)
    else:
        logging.debug(
            "Skip pendding open (solar_rad: {solar_rad:.1f} W/m^2, lux: {lux:.1f} LUX)".format(
                solar_rad=sense_data["solar_rad"]["value"],
                lux=sense_data["lux"]["value"],
            )
        )


def conv_schedule_time_to_datetime(schedule_time):
    return datetime.datetime.strptime(
        datetime.datetime.now().strftime("%Y/%m/%d ") + schedule_time,
        "%Y/%m/%d %H:%M",
    )


def shutter_auto_close(config):
    if not schedule_data["close"]["is_active"]:
        return
    elif (
        datetime.datetime.now() < conv_schedule_time_to_datetime(schedule_data["open"]["time"])
    ) or STAT_PENDING_OPEN.exists():
        # NOTE: 開ける時刻よりも早い場合は処理しない
        return
    elif conv_schedule_time_to_datetime(schedule_data["close"]["time"]) < datetime.datetime.now():
        # NOTE: スケジュールで閉めていた場合は処理しない
        return
    elif STAT_AUTO_CLOSE.exists() and (exec_check_elapsed_time(STAT_AUTO_CLOSE) <= 12 * 60 * 60):
        # NOTE: 12時間以内に自動で閉めていた場合は処理しない
        return

    sense_data = rasp_shutter_sensor.get_sensor_data(config)
    if check_brightness(sense_data, "close") == BRIGHTNESS_STATE.DARK:
        app_log(
            ("📝 予定より早いですが，暗くなってきたので閉めます．{sensor_text}").format(
                sensor_text=rasp_shutter_control.sensor_text(sense_data),
            )
        )

        exec_shutter_control(
            config,
            "close",
            rasp_shutter_control.CONTROL_MODE.AUTO,
            sense_data,
            "sensor",
        )
        exec_check_update(STAT_AUTO_CLOSE)

        # NOTE: まだ明るくなる可能性がある時間帯の場合，再度自動的に開けるようにする
        hour = datetime.datetime.now().hour
        if (5 < hour) and (hour < 13):
            exec_check_update(STAT_PENDING_OPEN)

    else:  # pragma: no cover
        # NOTE: pending close の制御は無いのでここには来ない．
        logging.debug(
            "Skip pendding close (solar_rad: {solar_rad:.1f} W/m^2, lux: {lux:.1f} LUX)".format(
                solar_rad=sense_data["solar_rad"]["value"],
                lux=sense_data["lux"]["value"],
            )
        )


def shutter_auto_control(config):
    hour = datetime.datetime.now().hour

    # NOTE: 時間帯によって自動制御の内容を分ける
    if (5 < hour) and (hour < 12):
        shutter_auto_open(config)

    if (5 < hour) and (hour < 20):
        shutter_auto_close(config)


def shutter_schedule_control(config, state):
    logging.info("Execute shcedule control")

    sense_data = rasp_shutter_sensor.get_sensor_data(config)

    if check_brightness(sense_data, state) == BRIGHTNESS_STATE.UNKNOWN:
        error_sensor = []

        if not sense_data["solar_rad"]["valid"]:
            error_sensor.append("日射センサ")
        if not sense_data["lux"]["valid"]:
            error_sensor.append("照度センサ")

        app_log(
            "😵 {error_sensor}の値が不明なので{state}るのを見合わせます．".format(
                error_sensor="と".join(error_sensor),
                state="開け" if state == "open" else "閉め",
            ),
            APP_LOG_LEVEL.ERROR,
        )
        return

    if state == "open":
        if check_brightness(sense_data, state) == BRIGHTNESS_STATE.DARK:
            app_log(
                "📝 まだ暗いので開けるのを見合わせます．{sensor_text}".format(sensor_text=rasp_shutter_control.sensor_text(sense_data))
            )

            rasp_shutter_control.cmd_hist_push(
                {
                    "cmd": "pending",
                    "state": state,
                }
            )

            # NOTE: 暗いので開けれなかったことを通知
            exec_check_update(STAT_PENDING_OPEN)
        else:
            # NOTE: ここにきたときのみ，スケジュールに従って開ける
            exec_shutter_control(
                config,
                state,
                rasp_shutter_control.CONTROL_MODE.SCHEDULE,
                sense_data,
                "scheduler",
            )
    else:
        STAT_PENDING_OPEN.unlink(missing_ok=True)
        exec_shutter_control(
            config,
            state,
            rasp_shutter_control.CONTROL_MODE.SCHEDULE,
            sense_data,
            "scheduler",
        )


def schedule_validate(schedule_data):
    if len(schedule_data) != 2:
        logging.warning("Count of entry is Invalid: {count}".format(count=len(schedule_data)))
        return False

    for name, entry in schedule_data.items():
        for key in ["is_active", "time", "wday", "solar_rad", "lux"]:
            if key not in entry:
                logging.warning("Does not contain {key}".format(key=key))
                return False
        if type(entry["is_active"]) != bool:
            logging.warning("Type of is_active is invalid: {type}".format(type=type(entry["is_active"])))
            return False
        if type(entry["lux"]) != int:
            logging.warning("Type of lux is invalid: {type}".format(type=type(entry["is_active"])))
            return False
        if type(entry["solar_rad"]) != int:
            logging.warning("Type of solar_rad is invalid: {type}".format(type=type(entry["is_active"])))
            return False
        if not re.compile(r"\d{2}:\d{2}").search(entry["time"]):
            logging.warning("Format of time is invalid: {time}".format(time=entry["time"]))
            return False
        if len(entry["wday"]) != 7:
            logging.warning("Count of wday is Invalid: {count}".format(count=len(entry["wday"])))
            return False
        for i, wday_flag in enumerate(entry["wday"]):
            if type(wday_flag) != bool:
                logging.warning("Type of wday[{i}] is Invalid: {type}".format(i=i, type=type(entry["wday"][i])))
                return False
    return True


def schedule_store(schedule_data):
    global schedule_lock
    try:
        with schedule_lock:
            SCHEDULE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULE_DATA_PATH, "wb") as f:
                pickle.dump(schedule_data, f)
    except:
        logging.error(traceback.format_exc())
        app_log("😵 スケジュール設定の保存に失敗しました。", APP_LOG_LEVEL.ERROR)
        pass


def schedule_load():
    global schedule_lock
    if SCHEDULE_DATA_PATH.exists():
        try:
            with schedule_lock:
                with open(SCHEDULE_DATA_PATH, "rb") as f:
                    schedule_data = pickle.load(f)
                    if schedule_validate(schedule_data):
                        return schedule_data
        except:
            logging.error(traceback.format_exc())
            app_log("😵 スケジュール設定の読み出しに失敗しました。", APP_LOG_LEVEL.ERROR)
            pass

    schedule_data = {
        "is_active": False,
        "time": "00:00",
        "solar_rad": 0,
        "lux": 0,
        "wday": [True] * 7,
    }

    return {
        "open": schedule_data | {"time": "08:00", "solar_rad": 150, "lux": 1000},
        "close": schedule_data | {"time": "17:00", "solar_rad": 80, "lux": 1200},
    }


def set_schedule(config, schedule_data):
    schedule.clear()

    for state, entry in schedule_data.items():
        if not entry["is_active"]:
            continue

        if entry["wday"][0]:
            schedule.every().sunday.at(entry["time"], TIMEZONE).do(shutter_schedule_control, config, state)
        if entry["wday"][1]:
            schedule.every().monday.at(entry["time"], TIMEZONE).do(shutter_schedule_control, config, state)
        if entry["wday"][2]:
            schedule.every().tuesday.at(entry["time"], TIMEZONE).do(shutter_schedule_control, config, state)
        if entry["wday"][3]:
            schedule.every().wednesday.at(entry["time"], TIMEZONE).do(shutter_schedule_control, config, state)
        if entry["wday"][4]:
            schedule.every().thursday.at(entry["time"], TIMEZONE).do(shutter_schedule_control, config, state)
        if entry["wday"][5]:
            schedule.every().friday.at(entry["time"], TIMEZONE).do(shutter_schedule_control, config, state)
        if entry["wday"][6]:
            schedule.every().saturday.at(entry["time"], TIMEZONE).do(shutter_schedule_control, config, state)

    for job in schedule.get_jobs():
        logging.info("Next run: {next_run}".format(next_run=job.next_run))

    logging.info("Time to next jobs is {idle} sec".format(idle=schedule.idle_seconds()))

    schedule.every().minutes.do(shutter_auto_control, config)


def schedule_worker(config, queue):
    global should_terminate
    global schedule_data

    sleep_sec = 0.4

    liveness_file = pathlib.Path(config["liveness"]["file"]["scheduler"])
    liveness_file.parent.mkdir(parents=True, exist_ok=True)

    logging.info("Load schedule")
    schedule_data = schedule_load()

    set_schedule(config, schedule_data)

    logging.info("Start schedule worker")

    while True:
        if should_terminate:
            break

        try:
            if not queue.empty():
                schedule_data = queue.get()
                set_schedule(config, schedule_data)
                schedule_store(schedule_data)

            schedule.run_pending()

            liveness_file.touch()

            logging.debug("Sleep {sleep_sec} sec...".format(sleep_sec=sleep_sec))
        except OverflowError:  # pragma: no cover
            # NOTE: テストする際，freezer 使って日付をいじるとこの例外が発生する
            logging.debug(traceback.format_exc())
            pass
        time.sleep(sleep_sec)

    logging.info("Terminate schedule worker")


if __name__ == "__main__":
    from multiprocessing import Queue
    from multiprocessing.pool import ThreadPool

    import logger

    from config import load_config

    logger.init("test", level=logging.DEBUG)

    def test_func():
        global should_terminate
        logging.info("TEST")

        should_terminate = True

    config = load_config()
    queue = Queue()

    init()

    pool = ThreadPool(processes=1)
    result = pool.apply_async(schedule_worker, (config, queue))

    exec_time = datetime.datetime.now() + datetime.timedelta(seconds=5)
    queue.put(
        {
            "open": {
                "time": exec_time.strftime("%H:%M"),
                "is_active": True,
                "wday": [True] * 7,
                "solar_rad": 0,
                "lux": 0,
                "func": test_func,
            }
        }
    )

    # NOTE: 終了するのを待つ
    result.get()
