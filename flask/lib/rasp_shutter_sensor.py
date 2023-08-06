# -*- coding: utf-8 -*-
# #!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytz
import sensor_data
from flask_cors import cross_origin
from flask_util import support_jsonp
from webapp_config import APP_URL_PREFIX

from flask import Blueprint, current_app, jsonify

blueprint = Blueprint("rasp-shutter-sensor", __name__, url_prefix=APP_URL_PREFIX)


def get_sensor_data(config):
    timezone = pytz.timezone("Asia/Tokyo")

    sense_data = {}
    for field in ["lux", "solar_rad"]:
        sensor = config["sensor"][field]
        data = sensor_data.fetch_data(
            config["sensor"]["influxdb"],
            sensor["measure"],
            sensor["hostname"],
            field,
            start="-1h",
            last=True,
        )
        if data["valid"]:
            sense_data[field] = {
                "value": data["value"][0],
                # NOTE: タイムゾーン情報を削除しておく．
                "time": timezone.localize((data["time"][0].replace(tzinfo=None))),
                "valid": True,
            }
        else:
            sense_data[field] = {
                "valid": False,
            }

    return sense_data


@blueprint.route("/api/sensor", methods=["GET"])
@support_jsonp
@cross_origin()
def api_sensor_data():
    return jsonify(get_sensor_data(current_app.config["CONFIG"]))
