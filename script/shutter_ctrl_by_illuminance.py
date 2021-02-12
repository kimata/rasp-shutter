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
import json
import os
import sys
import pathlib
import requests
import logging
import logging.handlers
import pprint

INFLUX_DB_HOST     = 'columbia'
SENSOR_HOST        = 'rasp-storeroom'
RAD_THRESHOLD      = 30

sys.path.append(os.path.join(os.path.dirname(__file__), '../flask'))
from config import CONTROL_ENDPOONT,EXE_HIST_FILE_FORMAT,EXE_RESV_FILE_FORMAT

class GZipRotator:
    def namer(name):
        return name + '.gz'

    def rotator(source, dest):
        with open(source, 'rb') as fs:
            with gzip.open(dest, 'wb') as fd:
                fd.writelines(fs)
        os.remove(source)

def get_logger():
    logger = logging.getLogger()
    log_handler = logging.handlers.RotatingFileHandler(
        '/dev/shm/shutter_ctrl_by_illuminance.log',
        encoding='utf8', maxBytes=1*1024*1024, backupCount=10,
    )
    log_handler.formatter = logging.Formatter(
        fmt='%(asctime)s %(levelname)s %(name)s :%(message)s',
        datefmt='%Y/%m/%d %H:%M:%S %Z'
    )
    log_handler.namer = GZipRotator.namer
    log_handler.rotator = GZipRotator.rotator

    logger.addHandler(log_handler)
    logger.setLevel(level=logging.INFO)

    return logger

# InfluxDB にアクセスしてセンサーデータを取得
def get_solar_rad(hostname, table, name, time_range):
    response = requests.get(
        'http://' + INFLUX_DB_HOST + ':8086/query',
        params = {
            'db': 'sensor',
            'q': (
                'SELECT MEDIAN({name}) FROM "{table}" WHERE (hostname=\'{hostname}\' AND time >= now() - ({time_range})) ' +
                'GROUP BY TIME({time_range}) LIMIT 1'
            ).format(table=table, hostname=hostname, name=name, time_range=time_range)
        }
    )

    columns = response.json()['results'][0]['series'][0]['columns']
    values = response.json()['results'][0]['series'][0]['values'][0]

    data = {}
    for i, key in enumerate(columns):
        data[key] = values[i]

    return data['median']


# auto = 0: 手動, 1: 自動(実際には制御しなかった場合にメッセージ有り), 2: 自動
def set_shutter_state(mode, auto):
    try:
        req = urllib.request.Request('{}?{}'.format(
            CONTROL_ENDPOONT['api']['ctrl'], urllib.parse.urlencode({
                'set': mode,
                'auto': auto,
            }))
        )
        status = json.loads(urllib.request.urlopen(req).read().decode())
        return status['result'] == 'success'
    except:
        pass

    return False


def log_message(message):
    try:
        req = urllib.request.Request('{}?{}'.format(
            CONTROL_ENDPOONT['api']['log'], urllib.parse.urlencode({
                'message': message,
            }))
        )
        status = json.loads(urllib.request.urlopen(req).read().decode())
        return status['result'] == 'success'
    except:
        pass

    return False


def process_open(cmd_type, solar_rad):
    exe_resv = pathlib.Path(EXE_RESV_FILE_FORMAT.format(mode='open'))

    if (cmd_type == 'ctrl'):
        if (solar_rad > RAD_THRESHOLD):
            return set_shutter_state('open', 1)
        else:
            log_message('周りが暗いので開けるのを延期しました．')
            exe_resv.touch()
            return True
    else:
        if (solar_rad > RAD_THRESHOLD) and exe_resv.exists():
            exe_resv.unlink(missing_ok=True)
            log_message('明るくなってきました．')
            return set_shutter_state('open', 2)
    return True


def process_close(cmd_type, solar_rad):
    exe_resv = pathlib.Path(EXE_RESV_FILE_FORMAT.format(mode='open'))
    exe_resv.unlink(missing_ok=True)

    if (cmd_type == 'ctrl'):
        return set_shutter_state('close', 1)
    else:
        if (solar_rad < RAD_THRESHOLD):
            log_message('周りが暗くなってきたので閉じます．')
            return set_shutter_state('close', 2)
    return True


def process_cmd(mode, cmd_type, solar_rad):
    if (mode == 'open'):
        return process_open(cmd_type, solar_rad)
    else:
        return process_close(cmd_type, solar_rad)


if __name__ == '__main__':
    arg = docopt(__doc__)

    logger = get_logger()
    solar_rad = get_solar_rad(SENSOR_HOST, 'sensor.raspberrypi', 'solar_rad', '5m')
    logger.info('solar_rad: {}'.format(solar_rad))

    if (arg['TYPE'] is None): # docopt の default がなぜか効かない...
        arg['TYPE'] = 'ctrl'

    process_cmd(arg['MODE'], arg['TYPE'], solar_rad)
