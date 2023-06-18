#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib

APP_URL_PREFIX = "/rasp-shutter"
STATIC_FILE_PATH = "../../dist"

SCHEDULE_DATA_PATH = pathlib.Path(__file__).parent.parent / "data" / "schedule.dat"
LOG_DB_PATH = pathlib.Path(__file__).parent.parent / "data" / "log.db"

STAT_DIR_PATH = pathlib.Path(__file__).parent.parent / "data" / "stat"

STAT_EXEC = {
    "open": STAT_DIR_PATH / "exe" / "open",
    "close": STAT_DIR_PATH / "exe" / "close",
}
# EXE_RESV_FILE_FORMAT = "/dev/shm/shutter_resv_{mode}"
