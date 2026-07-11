#!/usr/bin/env python3
# ruff: noqa: S101
"""センサーAPIの統合テスト

NOTE: get_sensor_data() はセッションスコープの sensor_data_mock でモックされるため、
ここでは「センサーデータが API レスポンスに正しく反映されること」を検証する。
InfluxDB 経路の実装（get_sensor_data_impl）は tests/unit/test_sensor_logic.py で検証する。
"""

from tests.fixtures.sensor_factory import SensorDataFactory
from tests.helpers.api_utils import SensorAPI


class TestSensorRead:
    """センサー読み取りテスト"""

    def test_sensor_read(self, client):
        """センサーデータを読み取れる（デフォルトは明るい状態）"""
        sensor_api = SensorAPI(client)

        result = sensor_api.get()

        for field in ["lux", "solar_rad", "altitude"]:
            assert field in result
            assert result[field]["valid"] is True
            assert isinstance(result[field]["value"], int | float)

    def test_sensor_custom_values(self, client, mock_sensor_data):
        """設定したセンサー値がレスポンスに反映される"""
        mock_sensor_data(SensorDataFactory.custom(solar_rad=200.5, lux=1500.25, altitude=30.75))

        sensor_api = SensorAPI(client)
        result = sensor_api.get()

        assert result["solar_rad"]["value"] == 200.5
        assert result["lux"]["value"] == 1500.25
        assert result["altitude"]["value"] == 30.75

    def test_sensor_invalid_lux(self, client, mock_sensor_data):
        """照度が無効な場合、valid フラグが False になる"""
        mock_sensor_data(SensorDataFactory.invalid_lux())

        sensor_api = SensorAPI(client)
        result = sensor_api.get()

        assert result["lux"]["valid"] is False
        assert result["lux"]["value"] is None
        assert result["solar_rad"]["valid"] is True

    def test_sensor_all_invalid(self, client, mock_sensor_data):
        """全センサーが無効な場合"""
        mock_sensor_data(SensorDataFactory.all_invalid())

        sensor_api = SensorAPI(client)
        result = sensor_api.get()

        for field in ["lux", "solar_rad", "altitude"]:
            assert result[field]["valid"] is False
