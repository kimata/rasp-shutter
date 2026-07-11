#!/usr/bin/env python3
# ruff: noqa: S101
"""シャッター制御APIの統合テスト"""

import os
import time

from tests.helpers.api_utils import CtrlLogAPI, ShutterAPI
from tests.helpers.assertions import CtrlLogChecker, LogChecker, SlackChecker
from tests.helpers.time_utils import setup_midnight_time


class TestShutterControlRead:
    """シャッター制御状態読み取りテスト

    NOTE: time_machineで深夜に設定し、センサーベースの自動制御が発動しないようにする。
    """

    def test_shutter_ctrl_read(self, client, time_machine):
        """シャッター状態を読み取れる"""
        setup_midnight_time(client, time_machine)

        shutter_api = ShutterAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        result = shutter_api.get_state()

        assert result["result"] == "success"

        ctrl_checker.wait_and_check([])
        log_checker.wait_and_check(["CLEAR"])
        slack_checker.check_no_error()

    def test_shutter_list(self, client, time_machine):
        """シャッターリストを取得できる"""
        setup_midnight_time(client, time_machine)

        shutter_api = ShutterAPI(client)

        result = shutter_api.get_list()

        assert result is not None


class TestShutterControlManual:
    """シャッター手動制御テスト

    NOTE: time_machineで深夜に設定し、センサーベースの自動制御が発動しないようにする。
    """

    def test_shutter_ctrl_manual_single_open_close(self, client, time_machine):
        """単一シャッターの手動開閉"""
        setup_midnight_time(client, time_machine)

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

    def test_shutter_ctrl_manual_second_shutter(self, client, time_machine):
        """2番目のシャッターの手動開閉"""
        setup_midnight_time(client, time_machine)

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

    def test_shutter_ctrl_manual_all(self, client, time_machine):
        """全シャッターの手動操作"""
        setup_midnight_time(client, time_machine)

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
    """シャッター制御失敗テスト

    NOTE: time_machineで深夜に設定し、センサーベースの自動制御が発動しないようにする。
    """

    def test_shutter_ctrl_manual_fail(self, client, time_machine, mocker):
        """制御失敗時の動作"""
        setup_midnight_time(client, time_machine)

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

        # NOTE: 制御に失敗した場合、API は result="error" を返す
        shutter_api.open(index=1, expect_result="error")
        shutter_api.close(index=1)

        log_checker.wait_and_check(["CLEAR", "OPEN_FAIL", "CLOSE_MANUAL"])
        slack_checker.check_error_contains("手動で開けるのに失敗しました")

    def test_shutter_ctrl_close_fail_keeps_pending(self, client, time_machine, mocker):
        """閉め制御に失敗した場合、暗くて延期されていた開ける制御を取り消さない"""
        setup_midnight_time(client, time_machine)

        import my_lib.footprint

        import rasp_shutter.control.config

        shutter_api = ShutterAPI(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        # 暗くて開けるのを延期している状態を作る
        my_lib.footprint.update(rasp_shutter.control.config.STAT_PENDING_OPEN.to_path())

        mocker.patch("rasp_shutter.control.webapi.control.call_shutter_api", return_value=False)

        shutter_api.close(expect_result="error")

        # 失敗時は pending open を維持する
        assert my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_OPEN.to_path())

        mocker.stopall()

        shutter_api.close()

        # 成功したら pending open は取り消される
        assert not my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_OPEN.to_path())

        # NOTE: エラーログと Slack 通知は非同期に処理されるため、テスト終了前に
        # 到着を待って引き取る（次のテストの check_no_error() を壊さないようにする）
        log_checker.wait_and_check(["CLEAR", "CLOSE_FAIL", "CLOSE_FAIL", "CLOSE_MANUAL", "CLOSE_MANUAL"])
        slack_checker.check_error_contains("閉めるのに失敗しました")


class TestShutterControlPostponed:
    """見合わせ情報のレスポンステスト"""

    def test_shutter_ctrl_postponed_in_response(self, client, time_machine, config):
        """制御間隔が短い場合、レスポンスの postponed に対象シャッター名が入る"""
        setup_midnight_time(client, time_machine)

        shutter_api = ShutterAPI(client)

        result = shutter_api.open(index=0)
        assert result["postponed"] == []

        # 直後の同一操作は見合わせられ、postponed に名前が入る（result は success のまま）
        result = shutter_api.open(index=0)
        assert result["result"] == "success"
        assert result["postponed"] == [config.shutter[0].name]


class TestShutterControlValidation:
    """シャッター制御 API の入力検証テスト"""

    def test_shutter_ctrl_requires_post(self, client, time_machine):
        """cmd=1（制御）は GET では受け付けない（405）"""
        setup_midnight_time(client, time_machine)

        import rasp_shutter.config

        response = client.get(
            f"{rasp_shutter.config.URL_PREFIX}/api/shutter_ctrl",
            query_string={"cmd": 1, "state": "open"},
        )
        assert response.status_code == 405
        assert response.json is not None
        assert response.json["result"] == "error"

    def test_shutter_ctrl_invalid_index(self, client, time_machine):
        """範囲外の index は 400（負のインデックスで別シャッターが動くのを防ぐ）"""
        setup_midnight_time(client, time_machine)

        import rasp_shutter.config

        for invalid_index in [-2, 100]:
            response = client.post(
                f"{rasp_shutter.config.URL_PREFIX}/api/shutter_ctrl",
                query_string={"cmd": 1, "index": invalid_index, "state": "open"},
            )
            assert response.status_code == 400, invalid_index
            assert response.json is not None
            assert response.json["result"] == "error"

    def test_shutter_ctrl_invalid_state(self, client, time_machine):
        """open/close 以外の state は 400"""
        setup_midnight_time(client, time_machine)

        import rasp_shutter.config

        response = client.post(
            f"{rasp_shutter.config.URL_PREFIX}/api/shutter_ctrl",
            query_string={"cmd": 1, "state": "foo"},
        )
        assert response.status_code == 400


class TestShutterStateInconsistent:
    """シャッター状態不整合テスト

    NOTE: time_machineで深夜に設定し、センサーベースの自動制御が発動しないようにする。
    """

    def test_shutter_ctrl_inconsistent_read(self, client, time_machine, config):
        """open/close両方のファイルが存在する場合の状態判定"""
        setup_midnight_time(client, time_machine)

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
