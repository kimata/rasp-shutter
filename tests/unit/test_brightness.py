#!/usr/bin/env python3
# ruff: noqa: S101
"""明るさ判定のユニットテスト"""

import pytest

from tests.fixtures.sensor_factory import SensorDataFactory


class TestBrightnessCheck:
    """check_brightness関数のテスト"""

    @pytest.fixture(autouse=True)
    def setup_schedule_data(self):
        """スケジュールデータのセットアップ"""
        import rasp_shutter.control.scheduler

        schedule_data = {
            "open": {
                "is_active": True,
                "time": "07:00",
                "solar_rad": 150,
                "lux": 1000,
                "altitude": 10,
                "wday": [True] * 7,
            },
            "close": {
                "is_active": True,
                "time": "17:00",
                "solar_rad": 80,
                "lux": 1200,
                "altitude": 15,
                "wday": [True] * 7,
            },
        }
        rasp_shutter.control.scheduler.set_schedule_data(schedule_data)
        yield
        rasp_shutter.control.scheduler.set_schedule_data(None)

    def test_check_brightness_bright_for_open(self):
        """開ける条件: 明るい場合 -> BRIGHT"""
        import rasp_shutter.control.scheduler

        sense_data = SensorDataFactory.bright()
        result = rasp_shutter.control.scheduler.check_brightness(sense_data, "open")

        assert result == rasp_shutter.control.scheduler.BRIGHTNESS_STATE.BRIGHT

    def test_check_brightness_dark_for_open(self):
        """開ける条件: 暗い場合 -> DARK"""
        import rasp_shutter.control.scheduler

        sense_data = SensorDataFactory.dark()
        result = rasp_shutter.control.scheduler.check_brightness(sense_data, "open")

        assert result == rasp_shutter.control.scheduler.BRIGHTNESS_STATE.DARK

    def test_check_brightness_dark_for_close(self):
        """閉める条件: 暗い場合 -> DARK"""
        import rasp_shutter.control.scheduler

        sense_data = SensorDataFactory.dark()
        result = rasp_shutter.control.scheduler.check_brightness(sense_data, "close")

        assert result == rasp_shutter.control.scheduler.BRIGHTNESS_STATE.DARK

    def test_check_brightness_bright_for_close(self):
        """閉める条件: 明るい場合 -> BRIGHT"""
        import rasp_shutter.control.scheduler

        sense_data = SensorDataFactory.bright()
        result = rasp_shutter.control.scheduler.check_brightness(sense_data, "close")

        assert result == rasp_shutter.control.scheduler.BRIGHTNESS_STATE.BRIGHT

    def test_check_brightness_invalid_lux(self):
        """照度センサー無効の場合 -> UNKNOWN"""
        import rasp_shutter.control.scheduler

        sense_data = SensorDataFactory.invalid_lux()
        result = rasp_shutter.control.scheduler.check_brightness(sense_data, "open")

        assert result == rasp_shutter.control.scheduler.BRIGHTNESS_STATE.UNKNOWN

    def test_check_brightness_invalid_solar_rad(self):
        """日射センサー無効の場合 -> UNKNOWN"""
        import rasp_shutter.control.scheduler

        sense_data = SensorDataFactory.invalid_solar_rad()
        result = rasp_shutter.control.scheduler.check_brightness(sense_data, "open")

        assert result == rasp_shutter.control.scheduler.BRIGHTNESS_STATE.UNKNOWN

    def test_check_brightness_boundary_open(self):
        """境界値テスト: 開ける条件の閾値付近"""
        import rasp_shutter.control.scheduler

        # 閾値ちょうど（すべてが閾値と同じ） -> DARK（超えていないのでDARK）
        sense_data = SensorDataFactory.custom(
            solar_rad=150,
            lux=1000,
            altitude=10,
        )
        result = rasp_shutter.control.scheduler.check_brightness(sense_data, "open")
        assert result == rasp_shutter.control.scheduler.BRIGHTNESS_STATE.DARK

        # 閾値を少し超える -> BRIGHT
        sense_data = SensorDataFactory.custom(
            solar_rad=151,
            lux=1001,
            altitude=11,
        )
        result = rasp_shutter.control.scheduler.check_brightness(sense_data, "open")
        assert result == rasp_shutter.control.scheduler.BRIGHTNESS_STATE.BRIGHT

    def test_check_brightness_boundary_close(self):
        """境界値テスト: 閉める条件の閾値付近"""
        import rasp_shutter.control.scheduler

        # 閾値ちょうど -> BRIGHTでもDARKでもない（閾値未満でDARK）
        sense_data = SensorDataFactory.custom(
            solar_rad=80,
            lux=1200,
            altitude=15,
        )
        result = rasp_shutter.control.scheduler.check_brightness(sense_data, "close")
        assert result == rasp_shutter.control.scheduler.BRIGHTNESS_STATE.BRIGHT

        # 閾値を少し下回る -> DARK
        sense_data = SensorDataFactory.custom(
            solar_rad=79,
            lux=1200,
            altitude=15,
        )
        result = rasp_shutter.control.scheduler.check_brightness(sense_data, "close")
        assert result == rasp_shutter.control.scheduler.BRIGHTNESS_STATE.DARK


class TestBrightnessText:
    """brightness_text関数のテスト"""

    def test_brightness_text_format(self):
        """brightness_textの出力形式を確認"""
        import rasp_shutter.control.scheduler

        sense_data = SensorDataFactory.bright()
        schedule_data = {
            "solar_rad": 150,
            "lux": 1000,
            "altitude": 10,
        }

        result = rasp_shutter.control.scheduler.brightness_text(sense_data, schedule_data)

        assert "solar_rad" in result
        assert "lux" in result
        assert "altitude" in result
        assert "current" in result
        assert "threshold" in result

    def test_brightness_text_comparison_operators(self):
        """比較演算子の表示確認"""
        import rasp_shutter.control.scheduler

        # 閾値より大きい
        sense_data = SensorDataFactory.custom(solar_rad=200, lux=2000, altitude=50)
        schedule_data = {"solar_rad": 150, "lux": 1000, "altitude": 10}
        result = rasp_shutter.control.scheduler.brightness_text(sense_data, schedule_data)
        assert ">" in result

        # 閾値より小さい
        sense_data = SensorDataFactory.custom(solar_rad=100, lux=500, altitude=5)
        result = rasp_shutter.control.scheduler.brightness_text(sense_data, schedule_data)
        assert "<" in result

        # 閾値と同じ
        sense_data = SensorDataFactory.custom(solar_rad=150, lux=1000, altitude=10)
        result = rasp_shutter.control.scheduler.brightness_text(sense_data, schedule_data)
        assert "=" in result
