# -*- coding: utf-8 -*-
# #!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import jsonify, Blueprint, current_app
import datetime
import pytz

import sensor_data
from webapp_config import APP_URL_PREFIX
from flask_util import support_jsonp, set_acao


blueprint = Blueprint("rasp-shutter-sensor", __name__, url_prefix=APP_URL_PREFIX)

config = None


@blueprint.before_app_first_request
def init():
    global config

    config = current_app.config["CONFIG"]


def get_sensor_data():
    timezone = pytz.timezone("Asia/Tokyo")

    sense_data = {}
    for field in ["lux", "solar_rad"]:
        sensor = config["sensor"][field]
        data = sensor_data.fetch_data(
            config["sensor"]["influxdb"],
            sensor["measure"],
            sensor["hostname"],
            field,
            "1h",
            last=True,
        )
        if data["valid"]:
            sense_data[field] = {
                "value": data["value"][0],
                # NOTE: 特に設定しないと InfluxDB は UTC 表記で
                # JST+9:00 の時刻を返す形になるので，ここで補正しておく．
                "time": timezone.localize(
                    (data["time"][0].utcnow() + datetime.timedelta(hours=9))
                ),
                "valid": True,
            }
        else:
            sense_data[field] = {
                "valid": False,
            }

    return sense_data


@blueprint.route("/api/sensor", methods=["GET"])
@support_jsonp
@set_acao
def api_sensor_data():
    return jsonify(get_sensor_data())
