#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import pathlib

import pytz

APP_URL_PREFIX = "/rasp-shutter"

TIMEZONE = datetime.timezone(datetime.timedelta(hours=+9), "JST")
TIMEZONE_PYTZ = pytz.timezone("Asia/Tokyo")  # schedule 用
TIMEZONE_OFFSET = "+9"

STATIC_FILE_PATH = pathlib.Path(__file__).parent.parent.parent / "dist"

DATA_PATH = pathlib.Path(__file__).parent.parent / "data"

SCHEDULE_DATA_PATH = DATA_PATH / "schedule.dat"
LOG_DB_PATH = DATA_PATH / "log.db"

STAT_DIR_PATH = DATA_PATH / "stat"

STAT_EXEC_TMPL = {
    "open": STAT_DIR_PATH / "exe" / "{index}_open",
    "close": STAT_DIR_PATH / "exe" / "{index}_close",
}

STAT_PENDING_OPEN = STAT_DIR_PATH / "pending" / "open"
STAT_AUTO_CLOSE = STAT_DIR_PATH / "auto" / "close"
