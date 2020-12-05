#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import json
import os
import sys
import requests
import pprint

INFLUX_DB_HOST     = 'columbia'
SENSOR_HOST        = 'rasp-storeroom'

sys.path.append(os.path.join(os.path.dirname(__file__), '../flask'))
from config import CONTROL_ENDPOONT


# InfluxDB にアクセスしてセンサーデータを取得
def get_solar_rad(hostname, table, name, time_range):
    response = requests.get(
        'http://' + INFLUX_DB_HOST + ':8086/query',
        params = {
            'db': 'sensor',
            'q': (
                'SELECT MEAN({name}) FROM "{table}" WHERE (hostname=\'{hostname}\' AND time >= now() - ({time_range})) ' +
                'GROUP BY TIME({time_range}) LIMIT 1'
            ).format(table=table, hostname=hostname, name=name, time_range=time_range)
        }
    )

    columns = response.json()['results'][0]['series'][0]['columns']
    values = response.json()['results'][0]['series'][0]['values'][0]

    data = {}
    for i, key in enumerate(columns):
        data[key] = values[i]

    return data['mean']


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
  solar_rad = get_solar_rad(SENSOR_HOST, 'sensor.raspberrypi', 'solar_rad', '15m')
  if (solar_rad < 40):
    set_shutter_state('close')
