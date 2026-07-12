#!/usr/bin/env python3
# ruff: noqa: S101
"""スケジューラー実行の統合テスト"""

from tests.fixtures.schedule_factory import ScheduleFactory, time_evening, time_morning, time_str
from tests.fixtures.sensor_factory import SensorDataFactory
from tests.helpers.api_utils import ScheduleAPI, ShutterAPI
from tests.helpers.assertions import CtrlLogChecker, LogChecker, SlackChecker
from tests.helpers.time_utils import (
    move_time_and_wait,
    setup_midnight_time,
)


class TestScheduleInactive:
    """スケジュール無効時のテスト"""

    def test_schedule_ctrl_inactive(self, client, time_machine, mock_sensor_data):
        """無効なスケジュールでは制御されない"""
        # 深夜に設定して自動制御が発動しないようにする
        setup_midnight_time(client, time_machine)

        # 明るい状態に設定して自動制御を防止
        mock_sensor_data(SensorDataFactory.bright())

        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        # 両方無効なスケジュール
        schedule_data = ScheduleFactory.inactive()
        schedule_data["open"]["time"] = time_str(time_morning(1))
        schedule_data["close"]["time"] = time_str(time_evening(1))
        schedule_api.update(schedule_data)

        # 朝の時刻に移動
        move_time_and_wait(time_machine, client, time_morning(1))
        move_time_and_wait(time_machine, client, time_morning(2))

        # 夕方の時刻に移動
        move_time_and_wait(time_machine, client, time_evening(1))
        move_time_and_wait(time_machine, client, time_evening(2))

        # 制御されていないことを確認
        ctrl_checker.wait_and_check([])
        log_checker.wait_and_check(["CLEAR", "SCHEDULE"])
        slack_checker.check_no_error()

    def test_schedule_ctrl_weekday_inactive(self, client, time_machine, mock_sensor_data):
        """曜日が無効なスケジュールでは制御されない"""
        # 深夜に設定して自動制御が発動しないようにする
        setup_midnight_time(client, time_machine)

        # 明るい状態に設定して自動制御を防止
        mock_sensor_data(SensorDataFactory.bright())

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

        # 朝の時刻に移動
        move_time_and_wait(time_machine, client, time_morning(1))
        move_time_and_wait(time_machine, client, time_morning(2))

        # 制御されていないことを確認
        ctrl_checker.wait_and_check([])
        log_checker.wait_and_check(["CLEAR", "SCHEDULE"])
        slack_checker.check_no_error()


class TestScheduleExecution:
    """スケジュール実行のテスト"""

    def test_schedule_ctrl_execute_close(self, client, time_machine, mock_sensor_data):
        """スケジュールに従って閉める"""
        # 深夜に設定して自動制御が発動しないようにする
        setup_midnight_time(client, time_machine)

        mock_sensor_data(SensorDataFactory.bright())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        # 先に開ける
        shutter_api.open()

        # 夕方に移動（スケジューラのループ完了を待機）
        move_time_and_wait(time_machine, client, time_evening(0))

        # シャッター1だけ閉める
        shutter_api.close(index=1)

        # 閉めるスケジュールを設定
        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            open_active=False,
        )
        schedule_api.update(schedule_data)

        # スケジュール時刻に移動
        move_time_and_wait(time_machine, client, time_evening(1))
        move_time_and_wait(time_machine, client, time_evening(2))

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


class TestPendingCloseRetry:
    """閉め制御失敗後の再試行テスト（F-2）"""

    def test_schedule_close_fail_retries_and_succeeds(self, client, mocker, time_machine, mock_sensor_data):
        """スケジュール閉め失敗後、リトライ間隔経過で再試行して閉める"""
        import my_lib.footprint

        import rasp_shutter.control.config

        setup_midnight_time(client, time_machine)

        mock_sensor_data(SensorDataFactory.bright())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)

        move_time_and_wait(time_machine, client, time_evening(0))

        shutter_api.open()

        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            open_active=False,
        )
        schedule_api.update(schedule_data)

        # スケジュール閉め制御が失敗する
        mocker.patch("rasp_shutter.control.scheduler.exec_shutter_control_impl", return_value=False)

        move_time_and_wait(time_machine, client, time_evening(1))
        move_time_and_wait(time_machine, client, time_evening(2))

        log_checker.wait_and_check(["CLEAR", "OPEN_MANUAL", "OPEN_MANUAL", "SCHEDULE", "FAIL_CONTROL"])

        # 失敗時は閉め再試行の footprint が設定される
        assert my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_CLOSE.to_path())

        # 制御が復旧したら、リトライ間隔経過後に再試行して閉まる
        mocker.stopall()
        move_time_and_wait(time_machine, client, time_evening(4))

        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
            ]
        )
        assert not my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_CLOSE.to_path())

        log_checker.wait_and_check(
            [
                "CLEAR",
                "OPEN_MANUAL",
                "OPEN_MANUAL",
                "SCHEDULE",
                "FAIL_CONTROL",
                "CLOSE_RETRY",
                "CLOSE_SCHEDULE",
                "CLOSE_SCHEDULE",
            ]
        )

    def test_schedule_close_fail_gives_up_after_expiry(self, client, mocker, time_machine, mock_sensor_data):
        """再試行の上限時間を超えたら諦めて Slack 通知する"""
        import my_lib.footprint
        import my_lib.time

        import rasp_shutter.control.config

        setup_midnight_time(client, time_machine)

        mock_sensor_data(SensorDataFactory.bright())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        move_time_and_wait(time_machine, client, time_evening(0))

        shutter_api.open()

        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            open_active=False,
        )
        schedule_api.update(schedule_data)

        mocker.patch("rasp_shutter.control.scheduler.exec_shutter_control_impl", return_value=False)

        move_time_and_wait(time_machine, client, time_evening(1))
        move_time_and_wait(time_machine, client, time_evening(2))

        assert my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_CLOSE.to_path())

        # 上限時間（6時間）を超えた時刻に移動
        expiry_time = my_lib.time.now().replace(hour=23, minute=30, second=0, microsecond=0)
        move_time_and_wait(time_machine, client, expiry_time)

        # footprint がクリアされ、Slack エラー通知される
        assert not my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_CLOSE.to_path())
        log_checker.wait_and_check(
            ["CLEAR", "OPEN_MANUAL", "OPEN_MANUAL", "SCHEDULE", "FAIL_CONTROL", "CLOSE_GIVEUP"]
        )
        slack_checker.check_error_contains("再試行を諦めました")


class TestScheduleControlFail:
    """スケジュール制御失敗テスト"""

    def test_schedule_ctrl_control_fail_impl(self, client, mocker, time_machine, mock_sensor_data):
        """制御実装が失敗する場合"""
        # 深夜に設定して自動制御が発動しないようにする
        setup_midnight_time(client, time_machine)

        mocker.patch("rasp_shutter.control.scheduler.exec_shutter_control_impl", return_value=False)
        mock_sensor_data(SensorDataFactory.dark())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        move_time_and_wait(time_machine, client, time_evening(0))

        shutter_api.open()

        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            open_active=False,
        )
        schedule_api.update(schedule_data)

        move_time_and_wait(time_machine, client, time_evening(1))
        move_time_and_wait(time_machine, client, time_evening(2))

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

    def test_schedule_close_fail_keeps_pending(self, client, mocker, time_machine, mock_sensor_data):
        """スケジュールの閉め制御が失敗した場合、pending open を維持する"""
        import my_lib.footprint

        import rasp_shutter.control.config

        setup_midnight_time(client, time_machine)

        mock_sensor_data(SensorDataFactory.dark())

        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)

        move_time_and_wait(time_machine, client, time_morning(0))

        # 開けるのは暗くて見合わせ（pending 設定）、その後の閉めるは失敗させる
        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_morning(5)),
        )
        schedule_api.update(schedule_data)

        move_time_and_wait(time_machine, client, time_morning(1))
        move_time_and_wait(time_machine, client, time_morning(2))

        ctrl_checker.wait_and_check([{"cmd": "pending", "state": "open"}])
        assert my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_OPEN.to_path())

        mocker.patch("rasp_shutter.control.scheduler.exec_shutter_control_impl", return_value=False)

        move_time_and_wait(time_machine, client, time_morning(5))
        move_time_and_wait(time_machine, client, time_morning(6))

        log_checker.wait_and_check(["CLEAR", "SCHEDULE", "OPEN_PENDING", "FAIL_CONTROL"])

        # 閉め制御に失敗した場合、暗くて延期されていた開ける制御は取り消されない
        assert my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_OPEN.to_path())

    def test_schedule_open_fail_sets_pending(self, client, mocker, time_machine, mock_sensor_data):
        """スケジュール開け制御が失敗した場合、pending open を設定して自動再試行する"""
        import my_lib.footprint

        import rasp_shutter.control.config

        setup_midnight_time(client, time_machine)

        mock_sensor_data(SensorDataFactory.bright())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)

        shutter_api.close()

        move_time_and_wait(time_machine, client, time_morning(0))

        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            close_active=False,
        )
        schedule_api.update(schedule_data)

        # 明るいのでスケジュールに従って開けようとするが、制御は失敗する
        mocker.patch("rasp_shutter.control.scheduler.exec_shutter_control_impl", return_value=False)

        move_time_and_wait(time_machine, client, time_morning(1))
        move_time_and_wait(time_machine, client, time_morning(2))

        log_checker.wait_and_check(["CLEAR", "CLOSE_MANUAL", "CLOSE_MANUAL", "SCHEDULE", "FAIL_CONTROL"])

        # 失敗時は pending open が設定され、自動再試行が有効になる
        assert my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_OPEN.to_path())

        # 制御が復旧したら、リトライ間隔経過後に自動で開ける
        mocker.stopall()
        move_time_and_wait(time_machine, client, time_morning(4))

        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
                {"cmd": "pending", "state": "open"},
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
            ]
        )
        log_checker.wait_and_check(
            [
                "CLEAR",
                "CLOSE_MANUAL",
                "CLOSE_MANUAL",
                "SCHEDULE",
                "FAIL_CONTROL",
                "OPEN_BRIGHT",
                "OPEN_AUTO",
                "OPEN_AUTO",
            ]
        )

    def test_schedule_ctrl_control_fail_exception(self, client, mocker, time_machine, mock_sensor_data):
        """制御中に例外が発生する場合"""
        # 深夜に設定して自動制御が発動しないようにする
        setup_midnight_time(client, time_machine)

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

        move_time_and_wait(time_machine, client, time_evening(0))

        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            open_active=False,
        )
        schedule_api.update(schedule_data)

        move_time_and_wait(time_machine, client, time_evening(1))
        move_time_and_wait(time_machine, client, time_evening(2))

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
