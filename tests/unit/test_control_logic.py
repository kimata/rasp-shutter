#!/usr/bin/env python3
# ruff: noqa: S101
"""制御ロジックのユニットテスト"""

import pathlib


class TestTimeStr:
    """time_str関数のテスト"""

    def test_time_str_hour(self):
        """時間単位の表示"""
        import rasp_shutter.control.webapi.control

        assert rasp_shutter.control.webapi.control.time_str(3600) == "1時間"
        assert rasp_shutter.control.webapi.control.time_str(7200) == "2時間"

    def test_time_str_hour_and_minutes(self):
        """時間と分の表示"""
        import rasp_shutter.control.webapi.control

        assert rasp_shutter.control.webapi.control.time_str(3660) == "1時間1分"
        assert rasp_shutter.control.webapi.control.time_str(7260) == "2時間1分"

    def test_time_str_seconds(self):
        """秒単位の表示"""
        import rasp_shutter.control.webapi.control

        assert rasp_shutter.control.webapi.control.time_str(50) == "50秒"
        assert rasp_shutter.control.webapi.control.time_str(30) == "30秒"

    def test_time_str_minutes_and_seconds(self):
        """分と秒の表示"""
        import rasp_shutter.control.webapi.control

        assert rasp_shutter.control.webapi.control.time_str(90) == "1分30秒"
        assert rasp_shutter.control.webapi.control.time_str(150) == "2分30秒"


class TestShutterState:
    """SHUTTER_STATE enumのテスト"""

    def test_shutter_state_values(self):
        """シャッター状態の値確認"""
        import rasp_shutter.control.webapi.control

        assert rasp_shutter.control.webapi.control.SHUTTER_STATE.OPEN == 0
        assert rasp_shutter.control.webapi.control.SHUTTER_STATE.CLOSE == 1
        assert rasp_shutter.control.webapi.control.SHUTTER_STATE.UNKNOWN == 2


class TestControlMode:
    """CONTROL_MODE enumのテスト"""

    def test_control_mode_values(self):
        """制御モードの値確認"""
        import rasp_shutter.control.webapi.control

        assert rasp_shutter.control.webapi.control.CONTROL_MODE.MANUAL.value == "🔧手動"
        assert rasp_shutter.control.webapi.control.CONTROL_MODE.SCHEDULE.value == "⏰スケジューラ"
        assert rasp_shutter.control.webapi.control.CONTROL_MODE.AUTO.value == "🤖自動"


class TestExecStatFile:
    """exec_stat_file関数のテスト"""

    def test_exec_stat_file_open(self):
        """openの状態ファイルパス生成"""
        import rasp_shutter.control.webapi.control

        result = rasp_shutter.control.webapi.control.exec_stat_file("open", 0)

        assert isinstance(result, pathlib.Path)
        assert "open" in str(result)
        assert "0" in str(result)

    def test_exec_stat_file_close(self):
        """closeの状態ファイルパス生成"""
        import rasp_shutter.control.webapi.control

        result = rasp_shutter.control.webapi.control.exec_stat_file("close", 1)

        assert isinstance(result, pathlib.Path)
        assert "close" in str(result)
        assert "1" in str(result)


class TestSensorText:
    """sensor_text関数のテスト"""

    def test_sensor_text_with_valid_data(self):
        """有効なセンサーデータのテキスト生成"""
        import rasp_shutter.control.webapi.control
        from tests.fixtures.sensor_factory import SensorDataFactory

        sense_data = SensorDataFactory.custom(
            solar_rad=200.5,
            lux=1500.3,
            altitude=30.2,
        )

        result = rasp_shutter.control.webapi.control.sensor_text(sense_data)

        assert "200.5" in result
        assert "1500.3" in result
        assert "30.2" in result

    def test_sensor_text_with_none_data(self):
        """センサーデータがNoneの場合"""
        import rasp_shutter.control.webapi.control

        result = rasp_shutter.control.webapi.control.sensor_text(None)

        # Noneの場合は空文字列を返す
        assert result == ""

    def test_sensor_text_with_invalid_data(self):
        """センサー値が無効な場合（TypeErrorにならず「?」表示になる）"""
        import rasp_shutter.control.webapi.control
        from tests.fixtures.sensor_factory import SensorDataFactory

        sense_data = SensorDataFactory.custom(
            solar_rad=200.5,
            lux_valid=False,
            altitude=30.2,
        )

        result = rasp_shutter.control.webapi.control.sensor_text(sense_data)

        assert "200.5" in result
        assert "?" in result
        assert "30.2" in result


class TestCallShutterApi:
    """call_shutter_api関数のテスト"""

    def test_connection_error_returns_false(self, monkeypatch):
        """ESP32に到達できない場合、例外ではなくFalseを返す"""
        import types

        import requests

        import rasp_shutter.config
        import rasp_shutter.control.webapi.control

        monkeypatch.setenv("DUMMY_MODE", "false")

        def raise_connection_error(*_args, **_kwargs):
            raise requests.exceptions.ConnectionError("connection refused")

        monkeypatch.setattr(requests, "get", raise_connection_error)

        shutter = rasp_shutter.config.ShutterConfig(
            name="test",
            endpoint=rasp_shutter.config.ShutterEndpointConfig(
                open="http://localhost:1/open",
                close="http://localhost:1/close",
            ),
        )
        config = types.SimpleNamespace(shutter=[shutter])

        result = rasp_shutter.control.webapi.control.call_shutter_api(config, 0, "open")  # type: ignore[arg-type]

        assert result is False


class TestCmdHist:
    """制御履歴のテスト"""

    def test_cmd_hist_push(self):
        """履歴の追加"""
        import rasp_shutter.control.webapi.control

        # クリア
        rasp_shutter.control.webapi.control.cmd_hist.clear()

        test_cmd = {"index": 0, "state": "open"}
        rasp_shutter.control.webapi.control.cmd_hist_push(test_cmd)

        assert len(rasp_shutter.control.webapi.control.cmd_hist) == 1
        assert rasp_shutter.control.webapi.control.cmd_hist[0] == test_cmd

        # クリーンアップ
        rasp_shutter.control.webapi.control.cmd_hist.clear()

    def test_cmd_hist_max_length(self):
        """履歴の最大長"""
        import rasp_shutter.control.webapi.control

        # クリア
        rasp_shutter.control.webapi.control.cmd_hist.clear()

        # 21件追加
        for i in range(25):
            rasp_shutter.control.webapi.control.cmd_hist_push({"index": i})

        # 最大20件に制限される
        assert len(rasp_shutter.control.webapi.control.cmd_hist) == 20

        # 最初の要素は5番目（0-4は削除されている）
        assert rasp_shutter.control.webapi.control.cmd_hist[0]["index"] == 5

        # クリーンアップ
        rasp_shutter.control.webapi.control.cmd_hist.clear()
