#!/usr/bin/env python3
"""スケジューラー実行の統合テスト"""

from tests.fixtures.schedule_factory import ScheduleFactory, time_evening, time_morning, time_str
from tests.fixtures.sensor_factory import SensorDataFactory
from tests.helpers.api_utils import ScheduleAPI, ShutterAPI
from tests.helpers.assertions import CtrlLogChecker, LogChecker, SlackChecker
from tests.helpers.time_utils import move_to, wait_for_schedule_update, wait_for_scheduler


class TestScheduleInactive:
    """スケジュール無効時のテスト"""

    def test_schedule_ctrl_inactive(self, client, time_machine):
        """無効なスケジュールでは制御されない"""
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        # 両方無効なスケジュール
        schedule_data = ScheduleFactory.inactive()
        schedule_data["open"]["time"] = time_str(time_morning(1))
        schedule_data["close"]["time"] = time_str(time_evening(1))
        schedule_api.update(schedule_data)
        wait_for_schedule_update()

        # 朝の時刻に移動
        move_to(time_machine, time_morning(1))
        wait_for_scheduler(5)

        move_to(time_machine, time_morning(2))
        wait_for_scheduler(5)

        # 夕方の時刻に移動
        move_to(time_machine, time_evening(1))
        wait_for_scheduler(5)

        move_to(time_machine, time_evening(2))
        wait_for_scheduler(5)

        # 制御されていないことを確認
        ctrl_checker.wait_and_check([])
        log_checker.wait_and_check(["CLEAR", "SCHEDULE"])
        slack_checker.check_no_error()

    def test_schedule_ctrl_weekday_inactive(self, client, time_machine):
        """曜日が無効なスケジュールでは制御されない"""
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        # 曜日すべて無効なスケジュール
        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            wday=[False] * 7,
        )
        schedule_api.update(schedule_data)
        wait_for_schedule_update()

        # 朝の時刻に移動
        move_to(time_machine, time_morning(1))
        wait_for_scheduler(5)

        move_to(time_machine, time_morning(2))
        wait_for_scheduler(5)

        # 制御されていないことを確認
        ctrl_checker.wait_and_check([])
        log_checker.wait_and_check(["CLEAR", "SCHEDULE"])
        slack_checker.check_no_error()


class TestScheduleExecution:
    """スケジュール実行のテスト"""

    def test_schedule_ctrl_execute_close(self, client, time_machine, mock_sensor_data):
        """スケジュールに従って閉める"""
        mock_sensor_data(SensorDataFactory.bright())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        # 先に開ける
        shutter_api.open()

        # 夕方に移動
        move_to(time_machine, time_evening(0))

        # シャッター1だけ閉める
        shutter_api.close(index=1)

        # 閉めるスケジュールを設定
        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            open_active=False,
        )
        schedule_api.update(schedule_data)
        wait_for_schedule_update()

        # スケジュール時刻に移動
        move_to(time_machine, time_evening(1))
        wait_for_scheduler(5)

        move_to(time_machine, time_evening(2))
        wait_for_scheduler(5)

        # シャッター0だけ閉まったことを確認
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
                {"index": 1, "state": "close"},
                {"index": 0, "state": "close"},
            ]
        )

        log_checker.wait_and_check(
            [
                "CLEAR",
                "OPEN_MANUAL",
                "OPEN_MANUAL",
                "CLOSE_MANUAL",
                "SCHEDULE",
                "CLOSE_SCHEDULE",
                "CLOSE_PENDING",
            ]
        )
        slack_checker.check_no_error()


class TestScheduleControlFail:
    """スケジュール制御失敗テスト"""

    def test_schedule_ctrl_control_fail_impl(self, client, mocker, time_machine, mock_sensor_data):
        """制御実装が失敗する場合"""
        mocker.patch("rasp_shutter.control.scheduler.exec_shutter_control_impl", return_value=False)
        mock_sensor_data(SensorDataFactory.dark())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        move_to(time_machine, time_evening(0))

        shutter_api.open()

        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            open_active=False,
        )
        schedule_api.update(schedule_data)
        wait_for_schedule_update()

        move_to(time_machine, time_evening(1))
        wait_for_scheduler(5)

        move_to(time_machine, time_evening(2))
        wait_for_scheduler(5)

        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
            ]
        )

        log_checker.wait_and_check(
            [
                "CLEAR",
                "OPEN_MANUAL",
                "OPEN_MANUAL",
                "SCHEDULE",
                "FAIL_CONTROL",
            ]
        )
        slack_checker.check_no_error()

    def test_schedule_ctrl_control_fail_exception(self, client, mocker, time_machine, mock_sensor_data):
        """制御中に例外が発生する場合"""
        mock_sensor_data(SensorDataFactory.bright())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        shutter_api.open()

        mocker.patch(
            "rasp_shutter.control.scheduler.rasp_shutter.control.webapi.control.set_shutter_state",
            side_effect=RuntimeError(),
        )

        move_to(time_machine, time_evening(0))

        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            open_active=False,
        )
        schedule_api.update(schedule_data)
        wait_for_schedule_update()

        move_to(time_machine, time_evening(1))
        wait_for_scheduler(5)

        move_to(time_machine, time_evening(2))
        wait_for_scheduler(5)

        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
            ]
        )

        log_checker.wait_and_check(
            [
                "CLEAR",
                "OPEN_MANUAL",
                "OPEN_MANUAL",
                "SCHEDULE",
                "FAIL_CONTROL",
            ]
        )
        slack_checker.check_no_error()
