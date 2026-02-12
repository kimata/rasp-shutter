#!/usr/bin/env python3
import dataclasses
import datetime

import flask
import flask_cors
import my_lib.sensor_data
import my_lib.time
import my_lib.webapp.config
import pysolar.solar

import rasp_shutter.config
import rasp_shutter.type_defs

blueprint = flask.Blueprint("rasp-shutter-sensor", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)


def get_solar_altitude(config: rasp_shutter.config.AppConfig) -> rasp_shutter.type_defs.SensorValue:
    # pysolar.solar.get_altitude() はUTC時刻を要求するため、明示的にUTCを使用
    now = datetime.datetime.now(datetime.UTC)
    return rasp_shutter.type_defs.SensorValue.create_valid(
        value=pysolar.solar.get_altitude(config.location.latitude, config.location.longitude, now),
        time=now,
    )


def get_sensor_data(config: rasp_shutter.config.AppConfig) -> rasp_shutter.type_defs.SensorData:
    timezone = my_lib.time.get_zoneinfo()

    sensor_values: dict[str, rasp_shutter.type_defs.SensorValue] = {}
    for field in ["lux", "solar_rad"]:
        sensor = getattr(config.sensor, field)
        data = my_lib.sensor_data.fetch_data(
            config.sensor.influxdb,
            sensor.measure,
            sensor.hostname,
            field,
            start="-1h",
            last=True,
        )
        if data.valid:
            sensor_values[field] = rasp_shutter.type_defs.SensorValue.create_valid(
                value=data.value[0],
                # NOTE: タイムゾーン情報を削除しておく。
                time=data.time[0].replace(tzinfo=timezone),
            )
        else:
            sensor_values[field] = rasp_shutter.type_defs.SensorValue.create_invalid()

    return rasp_shutter.type_defs.SensorData(
        lux=sensor_values["lux"],
        solar_rad=sensor_values["solar_rad"],
        altitude=get_solar_altitude(config),
    )


@blueprint.route("/api/sensor", methods=["GET"])
@flask_cors.cross_origin()
def api_sensor_data() -> flask.Response:
    config: rasp_shutter.config.AppConfig = flask.current_app.config["CONFIG"]
    return flask.jsonify(dataclasses.asdict(get_sensor_data(config)))
