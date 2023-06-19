#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import schedule
import time
import pickle
import traceback
import threading
import pathlib
import re

import rasp_shutter_control
from webapp_config import SCHEDULE_DATA_PATH
from webapp_log import app_log


RETRY_COUNT = 3

schedule_lock = None
should_terminate = False


def init():
    global schedule_lock
    schedule_lock = threading.Lock()


def shutter_auto_control_impl(state):
    try:
        # NOTE: Web 経由だと認証つけた場合に困るので，直接関数を呼ぶ
        # auto = 0: 手動, 1: 自動(実際には制御しなかった場合にメッセージ有り), 2: 自動(実際に制御した場合のみメッセージ)
        rasp_shutter_control.set_shutter_state(state, 1)
        return True
    except:
        logging.warning(traceback.format_exc())
        pass

    return False


def shutter_auto_control(mode):
    logging.info("Starts automatic control of the shutter")

    for i in range(RETRY_COUNT):
        if shutter_auto_control_impl(mode):
            return True

    app_log("😵 シャッターの自動制御に失敗しました。")
    return False


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
        app_log("😵 スケジュール設定の保存に失敗しました。")
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
            app_log("😵 スケジュール設定の読み出しに失敗しました。")
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
                shutter_auto_control, mode=name
            )
        if entry["wday"][1]:
            schedule.every().monday.at(entry["time"]).do(
                shutter_auto_control, mode=name
            )
        if entry["wday"][2]:
            schedule.every().tuesday.at(entry["time"]).do(
                shutter_auto_control, mode=name
            )
        if entry["wday"][3]:
            schedule.every().wednesday.at(entry["time"]).do(
                shutter_auto_control, mode=name
            )
        if entry["wday"][4]:
            schedule.every().thursday.at(entry["time"]).do(
                shutter_auto_control, mode=name
            )
        if entry["wday"][5]:
            schedule.every().friday.at(entry["time"]).do(
                shutter_auto_control, mode=name
            )
        if entry["wday"][6]:
            schedule.every().saturday.at(entry["time"]).do(
                shutter_auto_control, mode=name
            )

    for job in schedule.get_jobs():
        logging.info("Next run: {next_run}".format(next_run=job.next_run))


def schedule_worker(config, queue):
    global should_terminate

    sleep_sec = 1

    liveness_file = pathlib.Path(config["liveness"]["file"]["scheduler"])
    liveness_file.parent.mkdir(parents=True, exist_ok=True)

    logging.info("Load schedule")
    set_schedule(schedule_load())

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
    import datetime
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
