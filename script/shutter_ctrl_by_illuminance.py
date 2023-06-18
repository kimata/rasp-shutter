#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Usage:
    shutter_ctrl_by_illuminance.py MODE [TYPE]

Options:
    MODE    mode of control (open | close)
    TYPE    type of control (check | ctrl) [default: ctrl]
"""
from docopt import docopt

import urllib.request
import yaml
import json
import os
import sys
import pathlib
import logging
import logging.handlers
import gzip

import influxdb_client

FLUX_QUERY = """
from(bucket: "{bucket}")
    |> range(start: -{period})
    |> filter(fn:(r) => r._measurement == "{measure}")
    |> filter(fn: (r) => r.hostname == "{hostname}")
    |> filter(fn: (r) => r["_field"] == "{param}")
    |> aggregateWindow(every: 3m, fn: mean, createEmpty: false)
    |> exponentialMovingAverage(n: 3)
    |> sort(columns: ["_time"], desc: true)
    |> limit(n: 1)
"""

SENSOR = {
    "LUX_0": {
        "NAME": "outdoor",
        "HOST": "rasp-meter-8",
        "PARAM": "lux",
        "OPEN_TH": 1000,
        "CLOSE_TH": 1200,
        "FORMAT": "{:.0f} LUX",
    },
    "LUX_1": {
        "NAME": "utility room",
        "HOST": "rpi-cm4-sensor-4",
        "PARAM": "lux",
        "OPEN_TH": 1000,
        "CLOSE_TH": 1200,
        "FORMAT": "{:.0f} LUX",
    },
    "RAD": {
        "NAME": "outdoor",
        "HOST": "rasp-storeroom",
        "PARAM": "solar_rad",
        "OPEN_TH": 150,
        "CLOSE_TH": 80,
        "FORMAT": "{:.0f} W",
    },
}


sys.path.append(os.path.join(os.path.dirname(__file__), "../flask"))
from config import CONTROL_ENDPOONT, EXE_HIST_FILE_FORMAT, EXE_RESV_FILE_FORMAT


CONFIG_PATH = "./config.yml"


def load_config():
    path = str(pathlib.Path(os.path.dirname(__file__), CONFIG_PATH))
    with open(path, "r") as file:
        return yaml.load(file, Loader=yaml.SafeLoader)


class GZipRotator:
    def namer(name):
        return name + ".gz"

    def rotator(source, dest):
        with open(source, "rb") as fs:
            with gzip.open(dest, "wb") as fd:
                fd.writelines(fs)
        os.remove(source)


def get_logger():
    logger = logging.getLogger()
    log_handler = logging.handlers.RotatingFileHandler(
        "/dev/shm/shutter_ctrl_by_illuminance.log",
        encoding="utf8",
        maxBytes=1 * 1024 * 1024,
        backupCount=10,
    )
    log_handler.formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s :%(message)s",
        datefmt="%Y/%m/%d %H:%M:%S %Z",
    )
    log_handler.namer = GZipRotator.namer
    log_handler.rotator = GZipRotator.rotator

    logger.addHandler(log_handler)
    logger.setLevel(level=logging.INFO)

    return logger


# InfluxDB にアクセスしてセンサーデータを取得
def get_db_value(config, hostname, measure, param):
    client = influxdb_client.InfluxDBClient(
        url=config["influxdb"]["url"],
        token=config["influxdb"]["token"],
        org=config["influxdb"]["org"],
    )

    query_api = client.query_api()

    table_list = query_api.query(
        query=FLUX_QUERY.format(
            bucket=config["influxdb"]["bucket"],
            measure=measure,
            hostname=hostname,
            param=param,
            period="1h",
        )
    )

    return table_list[0].records[0].get_value()


def get_sensor_value():
    config = load_config()

    return {
        stype: get_db_value(
            config, SENSOR[stype]["HOST"], "sensor.rasp", SENSOR[stype]["PARAM"]
        )
        for stype in SENSOR.keys()
    }


# auto = 0: 手動, 1: 自動(実際には制御しなかった場合にメッセージ有り), 2: 自動
def set_shutter_state(mode, auto):
    try:
        req = urllib.request.Request(
            "{}?{}".format(
                CONTROL_ENDPOONT["api"]["ctrl"],
                urllib.parse.urlencode({"set": mode, "auto": auto}),
            )
        )
        status = json.loads(urllib.request.urlopen(req).read().decode())
        return status["result"] == "success"
    except:
        pass

    return False


def log_message(message, logger):
    logger.info(message)
    try:
        req = urllib.request.Request(
            "{}?{}".format(
                CONTROL_ENDPOONT["api"]["log"],
                urllib.parse.urlencode({"message": message}),
            )
        )
        status = json.loads(urllib.request.urlopen(req).read().decode())
        return status["result"] == "success"
    except:
        pass

    return False


def is_light(sensor_data):
    for stype in SENSOR.keys():
        if sensor_data[stype] > SENSOR[stype]["OPEN_TH"]:
            return True
    return False


def is_dark(sensor_data):
    for stype in SENSOR.keys():
        if sensor_data[stype] > SENSOR[stype]["CLOSE_TH"]:
            return False
    return True


def process_open(cmd_type, sensor_data, logger):
    exe_resv = pathlib.Path(EXE_RESV_FILE_FORMAT.format(mode="open"))

    if cmd_type == "ctrl":
        if is_light(sensor_data):
            return set_shutter_state("open", 1)
        else:
            log_message("周りが暗いので開けるのを延期しました．", logger)
            exe_resv.touch()
            return True
    else:
        if is_light(sensor_data) and exe_resv.exists():
            exe_resv.unlink(missing_ok=True)
            log_message("明るくなってきました．", logger)
            return set_shutter_state("open", 1)
    return True


def process_close(cmd_type, sensor_data, logger):
    exe_resv = pathlib.Path(EXE_RESV_FILE_FORMAT.format(mode="open"))
    exe_resv.unlink(missing_ok=True)

    if cmd_type == "ctrl":
        return set_shutter_state("close", 1)
    else:
        exe_hist = pathlib.Path(EXE_HIST_FILE_FORMAT.format(mode="close"))
        if is_dark(sensor_data) and not exe_hist.exists():
            log_message("周りが暗くなってきたので閉じます．", logger)
            return set_shutter_state("close", 1)
    return True


def process_cmd(mode, cmd_type, sensor_data, logger):
    if mode == "open":
        return process_open(cmd_type, sensor_data, logger)
    else:
        return process_close(cmd_type, sensor_data, logger)


def sensor_text(sensor_data):
    text_list = []
    for stype in SENSOR.keys():
        text_list.append(
            "{}: {}".format(
                SENSOR[stype]["NAME"],
                SENSOR[stype]["FORMAT"].format(sensor_data[stype]),
            )
        )

    return ", ".join(text_list)


if __name__ == "__main__":
    arg = docopt(__doc__)

    logger = get_logger()
    sensor_data = get_sensor_value()
    logger.info(sensor_text(sensor_data))

    if arg["TYPE"] is None:  # docopt の default がなぜか効かない...
        arg["TYPE"] = "ctrl"

    process_cmd(arg["MODE"], arg["TYPE"], sensor_data, logger)
