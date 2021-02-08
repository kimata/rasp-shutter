#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import json
import os
import sys
import requests
import logging
import logging.handlers
import pprint

INFLUX_DB_HOST     = 'columbia'
SENSOR_HOST        = 'rasp-storeroom'
RAD_THRESHOLD      = 30

sys.path.append(os.path.join(os.path.dirname(__file__), '../flask'))
from config import CONTROL_ENDPOONT

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
        '/dev/shm/nightfall_ctrl.log',
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


def set_shutter_state(mode):
    try:
        req = urllib.request.Request('{}?{}'.format(
            CONTROL_ENDPOONT['api'], urllib.parse.urlencode({
                'set': mode,
                'auto': 2,
            }))
        )
        status = json.loads(urllib.request.urlopen(req).read().decode())
        return status['result'] == 'success'
    except:
        pass

    return False


if __name__ == '__main__':
    logger = get_logger()
    solar_rad = get_solar_rad(SENSOR_HOST, 'sensor.raspberrypi', 'solar_rad', '5m')
    logger.info('sorlar_rad: {}'.format(solar_rad))

    if (solar_rad < RAD_THRESHOLD):
        logger.info('set_shutter_state: {}'.format('CLOSE'))
        set_shutter_state('close')
