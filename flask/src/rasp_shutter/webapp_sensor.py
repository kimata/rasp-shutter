#!/usr/bin/env python3
import datetime

import flask_cors
import my_lib.flask_util
import my_lib.sensor_data
import my_lib.webapp.config
import pysolar.solar
import pytz

import flask

blueprint = flask.Blueprint("rasp-shutter-sensor", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)


def get_solar_altitude(config):
    return {
        "value": pysolar.solar.get_altitude(
            config["location"]["latitude"],
            config["location"]["longitude"],
            datetime.datetime.now(datetime.timezone.utc),
        )
    }


def get_sensor_data(config):
    timezone = pytz.timezone("Asia/Tokyo")

    sense_data = {}
    for field in ["lux", "solar_rad"]:
        sensor = config["sensor"][field]
        data = my_lib.sensor_data.fetch_data(
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
                "time": timezone.localize(data["time"][0].replace(tzinfo=None)),
                "valid": True,
            }
        else:
            sense_data[field] = {
                "valid": False,
            }

    sense_data["altitude"] = get_solar_altitude(config)

    return sense_data


@blueprint.route("/api/sensor", methods=["GET"])
@my_lib.flask_util.support_jsonp
@flask_cors.cross_origin()
def api_sensor_data():
    return flask.jsonify(get_sensor_data(flask.current_app.config["CONFIG"]))
