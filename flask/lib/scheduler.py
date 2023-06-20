#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import IntEnum
import logging
import schedule
import datetime
import time
import pickle
import traceback
import threading
import pathlib
import re

import rasp_shutter_control
import rasp_shutter_sensor
from webapp_config import SCHEDULE_DATA_PATH, STAT_PENDING_OPEN, STAT_AUTO_CLOSE
from webapp_log import app_log, APP_LOG_LEVEL


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


def check_brightness(sense_data, state):
    if (not sense_data["lux"]["valid"]) or (not sense_data["solar_rad"]["valid"]):
        return BRIGHTNESS_STATE.UNKNOWN

    if (sense_data["lux"]["value"] < schedule_data[state]["lux"]) or (
        sense_data["solar_rad"]["value"] < schedule_data[state]["solar_rad"]
    ):
        return BRIGHTNESS_STATE.DARK
    else:
        return BRIGHTNESS_STATE.BRIGHT


def exec_shutter_control_impl(state, mode):
    try:
        # NOTE: Web 経由だと認証つけた場合に困るので，直接関数を呼ぶ
        rasp_shutter_control.set_shutter_state(state, mode)
        return True
    except:
        logging.warning(traceback.format_exc())
        pass

    return False


def exec_shutter_control(state, mode):
    logging.info("Starts automatic control of the shutter")

    for i in range(RETRY_COUNT):
        if exec_shutter_control_impl(state, mode):
            return True

    app_log("😵 シャッターの制御に失敗しました。")
    return False


def shutter_auto_open():
    if not schedule_data["open"]["is_active"]:
        return

    if (not STAT_PENDING_OPEN.exists()) or (
        (
            datetime.datetime.now()
            - datetime.datetime.fromtimestamp(STAT_PENDING_OPEN.stat().st_mtime)
        ).total_seconds()
        > 12 * 60 * 60
    ):
        # NOTE: 暗くて開けるのを延期されている場合以外は処理を行わない．
        return

    sense_data = rasp_shutter_sensor.get_sensor_data()
    if check_brightness(sense_data, "close") == BRIGHTNESS_STATE.BRIGHT:
        app_log(
            (
                "📝 暗くて延期されていましたが，明るくなってきたので開けます．"
                + "(日射: {solar_rad:.1f} W/m^2, 照度: {lux:.1f} LUX)"
            ).format(
                solar_rad=sense_data["solar_rad"]["value"],
                lux=sense_data["lux"]["value"],
            )
        )

        exec_shutter_control("open", rasp_shutter_control.CONTROL_MODE.AUTO)
        STAT_PENDING_OPEN.unlink(missing_ok=True)


def shutter_auto_close():
    if not schedule_data["close"]["is_active"]:
        return

    if STAT_AUTO_CLOSE.exists() and (
        (
            datetime.datetime.now()
            - datetime.datetime.fromtimestamp(STAT_AUTO_CLOSE.stat().st_mtime)
        ).total_seconds()
        <= 12 * 60 * 60
    ):
        # NOTE: 12時間以内に自動で閉めていた場合は処理しない
        return

    sense_data = rasp_shutter_sensor.get_sensor_data()
    if check_brightness(sense_data, "close") == BRIGHTNESS_STATE.DARK:
        app_log(
            (
                "📝 予定より早いですが，暗くなってきたので閉めます．"
                + "(日射: {solar_rad:.1f} W/m^2, 照度: {lux:.1f} LUX)"
            ).format(
                solar_rad=sense_data["solar_rad"]["value"],
                lux=sense_data["lux"]["value"],
            )
        )

        exec_shutter_control("close", rasp_shutter_control.CONTROL_MODE.AUTO)
        STAT_AUTO_CLOSE.touch()


def shutter_auto_control():
    hour = datetime.datetime.now().hour

    # NOTE: 時間帯によって自動制御の内容を分ける
    if (5 < hour) and (hour < 12):
        return shutter_auto_open()
    elif (12 < hour) and (hour < 20):
        return shutter_auto_close()


def shutter_schedule_control(state):
    sense_data = rasp_shutter_sensor.get_sensor_data()

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
                "📝 まだ暗いので開けるのを見合わせます．(日射: {solar_rad:.1f} W/m^2, 照度: {lux:.1f} LUX)".format(
                    solar_rad=sense_data["solar_rad"]["value"],
                    lux=sense_data["lux"]["value"],
                )
            )
            # NOTE: 暗いので開けれなかったことを通知
            STAT_PENDING_OPEN.touch()
        else:
            # NOTE: ここにきたときのみ，スケジュールに従って開ける
            exec_shutter_control(state)
    else:
        STAT_PENDING_OPEN.unlink(missing_ok=True)
        exec_shutter_control(state)


def schedule_validate(schedule_data):
    if len(schedule_data) != 2:
        return False

    for name, entry in schedule_data.items():
        for key in ["is_active", "time", "wday", "solar_rad", "lux"]:
            if key not in entry:
                return False
        if type(entry["is_active"]) != bool:
            return False
        if type(entry["lux"]) != int:
            return False
        if type(entry["solar_rad"]) != int:
            return False
        if not re.compile(r"\d{2}:\d{2}").search(entry["time"]):
            return False
        if len(entry["wday"]) != 7:
            return False
        for wday_flag in entry["wday"]:
            if type(wday_flag) != bool:
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
    if SCHEDULE_DATA_PATH.exists():
        try:
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
        "open": schedule_data | {"time": "08:00", "solar_rad": 1000, "lux": 150},
        "close": schedule_data | {"time": "17:00", "solar_rad": 1200, "lux": 80},
    }


def set_schedule(schedule_data):
    schedule.clear()

    logging.info(schedule_data)

    for name, entry in schedule_data.items():
        if not entry["is_active"]:
            continue

        if entry["wday"][0]:
            schedule.every().sunday.at(entry["time"]).do(
                shutter_schedule_control, state=name
            )
        if entry["wday"][1]:
            schedule.every().monday.at(entry["time"]).do(
                shutter_schedule_control, state=name
            )
        if entry["wday"][2]:
            schedule.every().tuesday.at(entry["time"]).do(
                shutter_schedule_control, state=name
            )
        if entry["wday"][3]:
            schedule.every().wednesday.at(entry["time"]).do(
                shutter_schedule_control, state=name
            )
        if entry["wday"][4]:
            schedule.every().thursday.at(entry["time"]).do(
                shutter_schedule_control, state=name
            )
        if entry["wday"][5]:
            schedule.every().friday.at(entry["time"]).do(
                shutter_schedule_control, state=name
            )
        if entry["wday"][6]:
            schedule.every().saturday.at(entry["time"]).do(
                shutter_schedule_control, state=name
            )

    for job in schedule.get_jobs():
        logging.info("Next run: {next_run}".format(next_run=job.next_run))

    schedule.every().minutes.do(shutter_auto_control)


def schedule_worker(config, queue):
    global should_terminate
    global schedule_data

    sleep_sec = 1

    liveness_file = pathlib.Path(config["liveness"]["file"]["scheduler"])
    liveness_file.parent.mkdir(parents=True, exist_ok=True)

    logging.info("Load schedule")
    schedule_data = schedule_load()

    set_schedule(schedule_data)

    logging.info("Start schedule worker")

    while True:
        if not queue.empty():
            schedule_data = queue.get()
            set_schedule(schedule_data)
            schedule_store(schedule_data)

        schedule.run_pending()

        if should_terminate:
            break

        liveness_file.touch()

        logging.debug("Sleep {sleep_sec} sec...".format(sleep_sec=sleep_sec))
        time.sleep(sleep_sec)

    logging.info("Terminate schedule worker")


if __name__ == "__main__":
    from multiprocessing.pool import ThreadPool
    from multiprocessing import Queue
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