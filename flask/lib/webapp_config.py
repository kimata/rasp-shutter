#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib

APP_URL_PREFIX = "/rasp-shutter"
STATIC_FILE_PATH = "../../dist"

DATA_PATH = pathlib.Path(__file__).parent.parent / "data"

SCHEDULE_DATA_PATH = DATA_PATH / "schedule.dat"
LOG_DB_PATH = DATA_PATH / "log.db"

STAT_DIR_PATH = DATA_PATH / "stat"

STAT_EXEC = {
    "open": STAT_DIR_PATH / "exe" / "open",
    "close": STAT_DIR_PATH / "exe" / "close",
}

STAT_PENDING_OPEN = STAT_DIR_PATH / "pending" / "open"
STAT_AUTO_CLOSE = STAT_DIR_PATH / "auto" / "close"
