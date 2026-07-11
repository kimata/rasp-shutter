#!/usr/bin/env python3
# ruff: noqa: S101
"""get_sensor_data_impl（InfluxDB 経路）のユニットテスト

NOTE: 統合テストではセッションスコープの sensor_data_mock が get_sensor_data() を
モックするため、実装本体（get_sensor_data_impl）はここで直接テストする。
my_lib.sensor_data.fetch_data のみをモックし、valid 分岐・タイムゾーン処理・
太陽高度計算を検証する。
"""

import datetime

import my_lib.sensor_data
import my_lib.time


def _fetch_mock_factory(results: dict):
    """field 名に応じた SensorDataResult を返す fetch_data モックを生成"""

    def fetch_mock(influxdb, measure, hostname, field, **kwargs):
        return results[field]

    return fetch_mock


def _valid_result(value: float, time: datetime.datetime | None = None):
    if time is None:
        time = datetime.datetime.now(datetime.UTC)
    return my_lib.sensor_data.SensorDataResult(valid=True, value=[value], time=[time])


def _invalid_result():
    return my_lib.sensor_data.SensorDataResult(valid=False)


class TestGetSensorDataImpl:
    """get_sensor_data_impl のテスト"""

    def test_both_valid(self, config, mocker):
        """lux / solar_rad とも有効な場合"""
        import rasp_shutter.control.webapi.sensor

        mocker.patch(
            "my_lib.sensor_data.fetch_data",
            side_effect=_fetch_mock_factory(
                {"lux": _valid_result(1234.5), "solar_rad": _valid_result(150.5)}
            ),
        )

        result = rasp_shutter.control.webapi.sensor.get_sensor_data_impl(config)

        assert result.lux.valid is True
        assert result.lux.value == 1234.5
        assert result.solar_rad.valid is True
        assert result.solar_rad.value == 150.5

    def test_lux_invalid(self, config, mocker):
        """lux が無効な場合、lux のみ invalid になる"""
        import rasp_shutter.control.webapi.sensor

        mocker.patch(
            "my_lib.sensor_data.fetch_data",
            side_effect=_fetch_mock_factory({"lux": _invalid_result(), "solar_rad": _valid_result(150.5)}),
        )

        result = rasp_shutter.control.webapi.sensor.get_sensor_data_impl(config)

        assert result.lux.valid is False
        assert result.lux.value is None
        assert result.solar_rad.valid is True

    def test_solar_rad_invalid(self, config, mocker):
        """solar_rad が無効な場合、solar_rad のみ invalid になる"""
        import rasp_shutter.control.webapi.sensor

        mocker.patch(
            "my_lib.sensor_data.fetch_data",
            side_effect=_fetch_mock_factory({"lux": _valid_result(1000.0), "solar_rad": _invalid_result()}),
        )

        result = rasp_shutter.control.webapi.sensor.get_sensor_data_impl(config)

        assert result.lux.valid is True
        assert result.solar_rad.valid is False

    def test_both_invalid(self, config, mocker):
        """両方無効な場合"""
        import rasp_shutter.control.webapi.sensor

        mocker.patch(
            "my_lib.sensor_data.fetch_data",
            side_effect=_fetch_mock_factory({"lux": _invalid_result(), "solar_rad": _invalid_result()}),
        )

        result = rasp_shutter.control.webapi.sensor.get_sensor_data_impl(config)

        assert result.lux.valid is False
        assert result.solar_rad.valid is False
        # 太陽高度は InfluxDB に依存しないため常に有効
        assert result.altitude.valid is True

    def test_time_tzinfo_replaced(self, config, mocker):
        """取得時刻の tzinfo がローカルタイムゾーンに貼り替えられる"""
        import rasp_shutter.control.webapi.sensor

        fetch_time = datetime.datetime(2026, 7, 4, 12, 34, 56, tzinfo=datetime.UTC)
        mocker.patch(
            "my_lib.sensor_data.fetch_data",
            side_effect=_fetch_mock_factory(
                {"lux": _valid_result(1000.0, fetch_time), "solar_rad": _valid_result(100.0, fetch_time)}
            ),
        )

        result = rasp_shutter.control.webapi.sensor.get_sensor_data_impl(config)

        assert result.lux.time is not None
        # NOTE: my_lib が「UTC ラベルの壁時計時刻」を返す前提で tzinfo を貼り替えている
        # （壁時計の時分は維持され、tzinfo のみローカルになる）
        assert result.lux.time.tzinfo == my_lib.time.get_zoneinfo()
        assert result.lux.time.hour == fetch_time.hour
        assert result.lux.time.minute == fetch_time.minute

    def test_solar_altitude(self, config):
        """太陽高度が pysolar により計算される"""
        import rasp_shutter.control.webapi.sensor

        result = rasp_shutter.control.webapi.sensor.get_solar_altitude(config)

        assert result.valid is True
        assert result.value is not None
        assert -90.0 <= result.value <= 90.0
