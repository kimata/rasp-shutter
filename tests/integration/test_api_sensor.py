#!/usr/bin/env python3
# ruff: noqa: S101
"""センサーAPIの統合テスト"""

import datetime

import my_lib.sensor_data

from tests.helpers.api_utils import SensorAPI


class TestSensorRead:
    """センサー読み取りテスト"""

    def test_sensor_read(self, client):
        """センサーデータを読み取れる"""
        sensor_api = SensorAPI(client)

        result = sensor_api.get()

        assert result is not None

    def test_sensor_invalid_data(self, client, mocker):
        """センサーデータが無効な場合"""
        mocker.patch(
            "my_lib.sensor_data.fetch_data",
            return_value=my_lib.sensor_data.SensorDataResult(valid=False),
        )

        sensor_api = SensorAPI(client)
        result = sensor_api.get()

        assert result is not None

    def test_sensor_with_valid_data(self, client, mocker):
        """有効なセンサーデータ"""
        mocker.patch(
            "my_lib.sensor_data.fetch_data",
            return_value=my_lib.sensor_data.SensorDataResult(
                valid=True,
                value=[100],
                time=[datetime.datetime.now(datetime.UTC)],
            ),
        )

        sensor_api = SensorAPI(client)
        result = sensor_api.get()

        assert result is not None


class TestSensorDummy:
    """ダミーセンサーテスト"""

    def test_sensor_dummy_with_none_value(self, client, mocker):
        """Noneを含むセンサーデータ"""
        call_count = [0]

        def value_mock():
            call_count[0] += 1
            if call_count[0] == 1:
                return None
            return 1

        table_entry_mock = mocker.MagicMock()
        record_mock = mocker.MagicMock()
        query_api_mock = mocker.MagicMock()
        mocker.patch.object(record_mock, "get_value", side_effect=value_mock)
        mocker.patch.object(
            record_mock,
            "get_time",
            return_value=datetime.datetime.now(datetime.UTC),
        )
        table_entry_mock.__iter__.return_value = [record_mock, record_mock]
        type(table_entry_mock).records = table_entry_mock
        query_api_mock.query.return_value = [table_entry_mock]
        mocker.patch(
            "influxdb_client.InfluxDBClient.query_api",
            return_value=query_api_mock,
        )

        sensor_api = SensorAPI(client)
        result = sensor_api.get()

        assert result is not None


class TestSensorFailure:
    """センサー失敗テスト"""

    def test_sensor_query_error(self, client, mocker):
        """クエリエラー時"""
        mocker.patch("influxdb_client.InfluxDBClient.query_api", side_effect=RuntimeError())

        sensor_api = SensorAPI(client)
        result = sensor_api.get()

        assert result is not None

    def test_sensor_get_value_none(self, client, mocker):
        """get_valueがNoneを返す場合"""
        mocker.patch(
            "influxdb_client.client.flux_table.FluxRecord.get_value",
            return_value=None,
        )

        sensor_api = SensorAPI(client)
        result = sensor_api.get()

        assert result is not None
