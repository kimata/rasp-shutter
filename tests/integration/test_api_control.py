#!/usr/bin/env python3
# ruff: noqa: S101
"""シャッター制御APIの統合テスト"""

import os
import time

from tests.helpers.api_utils import CtrlLogAPI, ShutterAPI
from tests.helpers.assertions import CtrlLogChecker, LogChecker, SlackChecker


class TestShutterControlRead:
    """シャッター制御状態読み取りテスト"""

    def test_shutter_ctrl_read(self, client):
        """シャッター状態を読み取れる"""
        shutter_api = ShutterAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        result = shutter_api.get_state()

        assert result["result"] == "success"

        ctrl_checker.wait_and_check([])
        log_checker.wait_and_check(["CLEAR"])
        slack_checker.check_no_error()

    def test_shutter_list(self, client):
        """シャッターリストを取得できる"""
        shutter_api = ShutterAPI(client)

        result = shutter_api.get_list()

        assert result is not None


class TestShutterControlManual:
    """シャッター手動制御テスト"""

    def test_shutter_ctrl_manual_single_open_close(self, client):
        """単一シャッターの手動開閉"""
        shutter_api = ShutterAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        # シャッター0を開ける
        shutter_api.open(index=0)
        ctrl_checker.wait_and_check([{"index": 0, "state": "open"}])

        # シャッター0を閉める
        shutter_api.close(index=0)
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 0, "state": "close"},
            ]
        )

        log_checker.wait_and_check(["CLEAR", "OPEN_MANUAL", "CLOSE_MANUAL"])
        slack_checker.check_no_error()

    def test_shutter_ctrl_manual_second_shutter(self, client):
        """2番目のシャッターの手動開閉"""
        shutter_api = ShutterAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        # シャッター1を開ける
        shutter_api.open(index=1)
        ctrl_checker.wait_and_check([{"index": 1, "state": "open"}])

        # シャッター1を閉める
        shutter_api.close(index=1)
        ctrl_checker.wait_and_check(
            [
                {"index": 1, "state": "open"},
                {"index": 1, "state": "close"},
            ]
        )

        log_checker.wait_and_check(["CLEAR", "OPEN_MANUAL", "CLOSE_MANUAL"])
        slack_checker.check_no_error()

    def test_shutter_ctrl_manual_all(self, client):
        """全シャッターの手動操作"""
        shutter_api = ShutterAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        ctrl_log_api = CtrlLogAPI(client)

        # シャッター0を開ける
        shutter_api.open(index=0)
        ctrl_checker.wait_and_check([{"index": 0, "state": "open"}])

        # シャッター1を開ける
        shutter_api.open(index=1)
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
            ]
        )

        # シャッター1を閉める
        shutter_api.close(index=1)
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
                {"index": 1, "state": "close"},
            ]
        )

        # シャッター0を閉める
        shutter_api.close(index=0)
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
                {"index": 1, "state": "close"},
                {"index": 0, "state": "close"},
            ]
        )

        # ログをクリアして全シャッター操作
        ctrl_log_api.clear()

        # 全シャッターを開ける
        shutter_api.open()
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
            ]
        )

        # 全シャッターを閉める
        shutter_api.close()
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
            ]
        )

        # 既に閉まっているシャッターを閉めようとする
        shutter_api.close()
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
            ]
        )

        log_checker.wait_and_check(
            [
                "CLEAR",
                "OPEN_MANUAL",
                "OPEN_MANUAL",
                "CLOSE_MANUAL",
                "CLOSE_MANUAL",
                "OPEN_MANUAL",
                "OPEN_MANUAL",
                "CLOSE_MANUAL",
                "CLOSE_MANUAL",
                "CLOSE_PENDING",
                "CLOSE_PENDING",
            ]
        )


class TestShutterControlFailure:
    """シャッター制御失敗テスト"""

    def test_shutter_ctrl_manual_fail(self, client, mocker):
        """制御失敗時の動作"""
        import requests

        shutter_api = ShutterAPI(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        # 最初の呼び出しは失敗、2回目以降は成功
        call_count = [0]

        def request_mock(url, timeout):
            call_count[0] += 1
            response = requests.models.Response()
            if call_count[0] == 1:
                response.status_code = 500
            else:
                response.status_code = 200
            return response

        mocker.patch.dict(os.environ, {"DUMMY_MODE": "false"})
        mocker.patch("rasp_shutter.control.webapi.control.requests.get", side_effect=request_mock)

        shutter_api.open(index=1)
        shutter_api.close(index=1)

        log_checker.wait_and_check(["CLEAR", "OPEN_FAIL", "CLOSE_MANUAL"])
        slack_checker.check_error_contains("手動で開けるのに失敗しました")


class TestShutterStateInconsistent:
    """シャッター状態不整合テスト"""

    def test_shutter_ctrl_inconsistent_read(self, client, config):
        """open/close両方のファイルが存在する場合の状態判定"""
        import my_lib.footprint
        import rasp_shutter.control.webapi.control

        shutter_api = ShutterAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        # シャッター0: closeが後
        rasp_shutter.control.webapi.control.clean_stat_exec(config)
        my_lib.footprint.update(rasp_shutter.control.webapi.control.exec_stat_file("open", 0))
        time.sleep(0.1)
        my_lib.footprint.update(rasp_shutter.control.webapi.control.exec_stat_file("close", 0))

        result = shutter_api.get_state()
        assert result["state"][0]["state"] == rasp_shutter.control.webapi.control.SHUTTER_STATE.CLOSE
        assert result["state"][1]["state"] == rasp_shutter.control.webapi.control.SHUTTER_STATE.UNKNOWN

        # シャッター1: openが後
        rasp_shutter.control.webapi.control.clean_stat_exec(config)
        my_lib.footprint.update(rasp_shutter.control.webapi.control.exec_stat_file("close", 1))
        time.sleep(0.1)
        my_lib.footprint.update(rasp_shutter.control.webapi.control.exec_stat_file("open", 1))

        result = shutter_api.get_state()
        assert result["state"][1]["state"] == rasp_shutter.control.webapi.control.SHUTTER_STATE.OPEN
        assert result["state"][0]["state"] == rasp_shutter.control.webapi.control.SHUTTER_STATE.UNKNOWN

        ctrl_checker.wait_and_check([])
        log_checker.wait_and_check(["CLEAR"])
        slack_checker.check_no_error()
