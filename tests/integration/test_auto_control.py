#!/usr/bin/env python3
# ruff: noqa: S101
"""自動制御の統合テスト"""

from tests.fixtures.schedule_factory import ScheduleFactory, time_evening, time_morning, time_str
from tests.fixtures.sensor_factory import SensorDataFactory
from tests.helpers.api_utils import ScheduleAPI, ShutterAPI
from tests.helpers.assertions import CtrlLogChecker, LogChecker, SlackChecker
from tests.helpers.time_utils import move_time_and_wait, setup_midnight_time, wait_for_schedule_update_seq


class TestAutoClose:
    """自動閉め制御のテスト"""

    def test_schedule_ctrl_auto_close(self, client, time_machine, mock_sensor_data):
        """暗くなったら自動で閉める"""
        # 深夜に設定して自動制御が発動しないようにする
        setup_midnight_time(client, time_machine)

        sensor_data_mock = mock_sensor_data(SensorDataFactory.bright())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        move_time_and_wait(time_machine, client, time_evening(0))

        shutter_api.open()

        # 閉めるスケジュールを遅めに設定
        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(5)),
            open_active=False,
        )
        schedule_api.update(schedule_data)
        wait_for_schedule_update_seq(client)

        move_time_and_wait(time_machine, client, time_evening(1))
        move_time_and_wait(time_machine, client, time_evening(2))

        # まだ明るいので閉まっていない
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
            ]
        )

        # 暗くする
        sensor_data_mock.return_value = SensorDataFactory.dark()

        move_time_and_wait(time_machine, client, time_evening(3))
        move_time_and_wait(time_machine, client, time_evening(4))

        # 暗くなったので閉まった
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
            ]
        )

        # スケジュール時刻を過ぎても既に閉まっているので何もしない
        move_time_and_wait(time_machine, client, time_evening(5))
        move_time_and_wait(time_machine, client, time_evening(6))

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
                "SCHEDULE",
                "CLOSE_DARK",
                "CLOSE_AUTO",
                "CLOSE_AUTO",
                "CLOSE_PENDING",
                "CLOSE_PENDING",
            ]
        )
        slack_checker.check_no_error()


class TestAutoReopen:
    """自動再開制御のテスト"""

    def test_schedule_ctrl_auto_reopen(self, client, time_machine, mock_sensor_data):
        """暗くて開けれなかった後、明るくなったら開ける"""
        # 深夜に設定して自動制御が発動しないようにする
        setup_midnight_time(client, time_machine)

        sensor_data_mock = mock_sensor_data(SensorDataFactory.dark())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        # 閉める
        shutter_api.close()

        move_time_and_wait(time_machine, client, time_morning(0))

        # 開けるスケジュールを設定
        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(2)),
            close_time=time_str(time_evening(1)),
        )
        schedule_api.update(schedule_data)
        wait_for_schedule_update_seq(client)

        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
            ]
        )

        # スケジュール時刻に移動（まだ暗い）
        move_time_and_wait(time_machine, client, time_morning(2))
        move_time_and_wait(time_machine, client, time_morning(3))

        # 暗いので pending
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
                {"cmd": "pending", "state": "open"},
            ]
        )

        # 明るくする
        sensor_data_mock.return_value = SensorDataFactory.bright()

        move_time_and_wait(time_machine, client, time_morning(4))

        # 明るくなったので開いた
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
                {"cmd": "pending", "state": "open"},
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
            ]
        )

        # 暗くする
        sensor_data_mock.return_value = SensorDataFactory.dark()

        move_time_and_wait(time_machine, client, time_morning(5))

        # 自動で開けてから時間が経っていないので閉まらない
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
                {"cmd": "pending", "state": "open"},
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
            ]
        )

        # 時間を進める（5分以上）
        move_time_and_wait(time_machine, client, time_morning(10))

        # 閉まった
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
                {"cmd": "pending", "state": "open"},
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
            ]
        )

        log_checker.wait_and_check(
            [
                "CLEAR",
                "CLOSE_MANUAL",
                "CLOSE_MANUAL",
                "SCHEDULE",
                "OPEN_PENDING",
                "OPEN_BRIGHT",
                "OPEN_AUTO",
                "OPEN_AUTO",
                "CLOSE_DARK",
                "CLOSE_AUTO",
                "CLOSE_AUTO",
            ],
            timeout_sec=15,
        )
        slack_checker.check_no_error()


class TestPendingOpen:
    """開けるペンディング状態のテスト"""

    def test_schedule_ctrl_pending_open(self, client, time_machine, mock_sensor_data):
        """暗くて開けれなかった後、明るくなったら開ける"""
        # 深夜に設定して自動制御が発動しないようにする
        setup_midnight_time(client, time_machine)

        sensor_data_mock = mock_sensor_data(SensorDataFactory.dark())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        move_time_and_wait(time_machine, client, time_morning(0))

        shutter_api.close()

        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(3)),
            close_time=time_str(time_evening(1)),
            close_active=False,
        )
        schedule_api.update(schedule_data)
        wait_for_schedule_update_seq(client)

        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
            ]
        )

        move_time_and_wait(time_machine, client, time_morning(1))
        move_time_and_wait(time_machine, client, time_morning(2))
        move_time_and_wait(time_machine, client, time_morning(3))

        # 暗いので pending
        sensor_data_mock.return_value = SensorDataFactory.bright()

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
                "OPEN_PENDING",
                "OPEN_BRIGHT",
                "OPEN_AUTO",
                "OPEN_AUTO",
            ]
        )
        slack_checker.check_no_error()

    def test_schedule_ctrl_pending_open_inactive(self, client, time_machine, mock_sensor_data):
        """pending open後にスケジュールを無効にした場合"""
        # 深夜に設定して自動制御が発動しないようにする
        setup_midnight_time(client, time_machine)

        sensor_data_mock = mock_sensor_data(SensorDataFactory.dark())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        shutter_api.close()

        move_time_and_wait(time_machine, client, time_morning(0))

        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            close_active=False,
        )
        schedule_api.update(schedule_data)
        wait_for_schedule_update_seq(client)

        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
            ]
        )

        move_time_and_wait(time_machine, client, time_morning(1))
        move_time_and_wait(time_machine, client, time_morning(2))
        move_time_and_wait(time_machine, client, time_morning(3))

        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
                {"cmd": "pending", "state": "open"},
            ]
        )

        # pending open後にスケジュールを無効にする
        schedule_data = ScheduleFactory.inactive()
        schedule_api.update(schedule_data)
        wait_for_schedule_update_seq(client)

        sensor_data_mock.return_value = SensorDataFactory.bright()

        move_time_and_wait(time_machine, client, time_morning(4))
        move_time_and_wait(time_machine, client, time_morning(5))
        move_time_and_wait(time_machine, client, time_morning(6))

        # 無効なので開かない
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
                {"cmd": "pending", "state": "open"},
            ]
        )

        log_checker.wait_and_check(
            [
                "CLEAR",
                "CLOSE_MANUAL",
                "CLOSE_MANUAL",
                "SCHEDULE",
                "OPEN_PENDING",
                "SCHEDULE",
            ]
        )
        slack_checker.check_no_error()


class TestAutoControlFailure:
    """自動制御の制御失敗時のテスト

    制御に失敗した場合は footprint（pending open / auto close）を進めず、
    リトライ間隔（AUTO_CONTROL_RETRY_INTERVAL_SEC）経過後に再試行することを検証する。
    """

    def test_auto_open_failure_keeps_pending(self, client, mocker, time_machine, mock_sensor_data):
        """自動開け制御が失敗しても pending を維持し、リトライ間隔経過後に再試行して開ける"""
        import my_lib.footprint

        import rasp_shutter.control.config

        setup_midnight_time(client, time_machine)

        sensor_data_mock = mock_sensor_data(SensorDataFactory.dark())

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
        wait_for_schedule_update_seq(client)

        move_time_and_wait(time_machine, client, time_morning(1))
        move_time_and_wait(time_machine, client, time_morning(2))

        # 暗いので pending
        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
                {"cmd": "pending", "state": "open"},
            ]
        )

        # 明るくなったが、制御は失敗する
        mocker.patch("rasp_shutter.control.scheduler.exec_shutter_control_impl", return_value=False)
        sensor_data_mock.return_value = SensorDataFactory.bright()

        move_time_and_wait(time_machine, client, time_morning(3))

        log_checker.wait_and_check(
            [
                "CLEAR",
                "CLOSE_MANUAL",
                "CLOSE_MANUAL",
                "SCHEDULE",
                "OPEN_PENDING",
                "OPEN_BRIGHT",
                "FAIL_CONTROL",
            ]
        )

        # 制御に失敗しても pending は維持される
        assert my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_OPEN.to_path())

        # リトライ間隔内は再試行しない（ログが増えない）
        move_time_and_wait(time_machine, client, time_morning(4))
        log_checker.wait_and_check(
            [
                "CLEAR",
                "CLOSE_MANUAL",
                "CLOSE_MANUAL",
                "SCHEDULE",
                "OPEN_PENDING",
                "OPEN_BRIGHT",
                "FAIL_CONTROL",
            ]
        )

        # 制御が復旧したら、リトライ間隔経過後に自動で開ける
        mocker.stopall()
        move_time_and_wait(time_machine, client, time_morning(6))

        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
                {"cmd": "pending", "state": "open"},
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
            ]
        )
        assert not my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_OPEN.to_path())

        log_checker.wait_and_check(
            [
                "CLEAR",
                "CLOSE_MANUAL",
                "CLOSE_MANUAL",
                "SCHEDULE",
                "OPEN_PENDING",
                "OPEN_BRIGHT",
                "FAIL_CONTROL",
                "OPEN_BRIGHT",
                "OPEN_AUTO",
                "OPEN_AUTO",
            ]
        )

    def test_auto_close_failure_keeps_state(self, client, mocker, time_machine, mock_sensor_data):
        """自動閉め制御が失敗しても閉め履歴を進めず、リトライ間隔経過後に再試行して閉める"""
        import my_lib.footprint

        import rasp_shutter.control.config

        setup_midnight_time(client, time_machine)

        sensor_data_mock = mock_sensor_data(SensorDataFactory.bright())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)

        move_time_and_wait(time_machine, client, time_evening(0))

        shutter_api.open()

        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(30)),
            open_active=False,
        )
        schedule_api.update(schedule_data)
        wait_for_schedule_update_seq(client)

        # 「開けてから時間が経っていない」ガードを越える
        move_time_and_wait(time_machine, client, time_evening(3))

        # 暗くなったが、制御は失敗する
        mocker.patch("rasp_shutter.control.scheduler.exec_shutter_control_impl", return_value=False)
        sensor_data_mock.return_value = SensorDataFactory.dark()

        move_time_and_wait(time_machine, client, time_evening(4))

        log_checker.wait_and_check(
            [
                "CLEAR",
                "OPEN_MANUAL",
                "OPEN_MANUAL",
                "SCHEDULE",
                "CLOSE_DARK",
                "FAIL_CONTROL",
            ]
        )

        # 制御に失敗した場合は自動クローズ履歴を進めない
        assert not my_lib.footprint.exists(rasp_shutter.control.config.STAT_AUTO_CLOSE.to_path())

        # 制御が復旧したら、リトライ間隔経過後に自動で閉める
        mocker.stopall()
        move_time_and_wait(time_machine, client, time_evening(7))

        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
                {"index": 0, "state": "close"},
                {"index": 1, "state": "close"},
            ]
        )
        assert my_lib.footprint.exists(rasp_shutter.control.config.STAT_AUTO_CLOSE.to_path())

        log_checker.wait_and_check(
            [
                "CLEAR",
                "OPEN_MANUAL",
                "OPEN_MANUAL",
                "SCHEDULE",
                "CLOSE_DARK",
                "FAIL_CONTROL",
                "CLOSE_DARK",
                "CLOSE_AUTO",
                "CLOSE_AUTO",
            ]
        )


class TestSensorError:
    """センサーエラー時のテスト"""

    def test_schedule_ctrl_invalid_sensor_lux(self, client, time_machine, mock_sensor_data):
        """照度センサー無効時: 開けるのを見合わせて pending を設定し、復旧後に開ける (BUG-4)"""
        # 深夜に設定して自動制御が発動しないようにする
        setup_midnight_time(client, time_machine)

        sensor_data_mock = mock_sensor_data(SensorDataFactory.invalid_lux())

        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        move_time_and_wait(time_machine, client, time_morning(0))

        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            close_active=False,
        )
        schedule_api.update(schedule_data)

        # スケジューラーがスケジュールを処理するまで待機
        # （現在時刻07:00でスケジュールを設定し、07:01の予定を作成）
        wait_for_schedule_update_seq(client)

        move_time_and_wait(time_machine, client, time_morning(1))
        move_time_and_wait(time_machine, client, time_morning(2))

        # センサー無効なので開けるのを見合わせるが、復旧後に開けられるよう pending を設定する
        ctrl_checker.wait_and_check([{"cmd": "pending", "state": "open"}])
        log_checker.wait_and_check(["CLEAR", "SCHEDULE", "FAIL_SENSOR"])
        slack_checker.check_error_contains("センサの値が不明なので開けるのを見合わせました。")

        # センサーが復旧して明るくなったら自動で開ける
        sensor_data_mock.return_value = SensorDataFactory.bright()
        move_time_and_wait(time_machine, client, time_morning(3))

        ctrl_checker.wait_and_check(
            [
                {"cmd": "pending", "state": "open"},
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
            ]
        )
        log_checker.wait_and_check(
            ["CLEAR", "SCHEDULE", "FAIL_SENSOR", "OPEN_BRIGHT", "OPEN_AUTO", "OPEN_AUTO"]
        )

    def test_schedule_ctrl_invalid_sensor_solar_rad(self, client, time_machine, mock_sensor_data):
        """日射センサー無効時: 開けるのを見合わせて pending を設定し、復旧後に開ける (BUG-4)"""
        # 深夜に設定して自動制御が発動しないようにする
        setup_midnight_time(client, time_machine)

        sensor_data_mock = mock_sensor_data(SensorDataFactory.invalid_solar_rad())

        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        move_time_and_wait(time_machine, client, time_morning(0))

        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            close_active=False,
        )
        schedule_api.update(schedule_data)

        # スケジューラーがスケジュールを処理するまで待機
        wait_for_schedule_update_seq(client)

        move_time_and_wait(time_machine, client, time_morning(1))
        move_time_and_wait(time_machine, client, time_morning(2))

        # センサー無効なので開けるのを見合わせるが、復旧後に開けられるよう pending を設定する
        ctrl_checker.wait_and_check([{"cmd": "pending", "state": "open"}])
        log_checker.wait_and_check(["CLEAR", "SCHEDULE", "FAIL_SENSOR"])
        slack_checker.check_error_contains("センサの値が不明なので開けるのを見合わせました。")

        # センサーが復旧して明るくなったら自動で開ける
        sensor_data_mock.return_value = SensorDataFactory.bright()
        move_time_and_wait(time_machine, client, time_morning(3))

        ctrl_checker.wait_and_check(
            [
                {"cmd": "pending", "state": "open"},
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
            ]
        )
        log_checker.wait_and_check(
            ["CLEAR", "SCHEDULE", "FAIL_SENSOR", "OPEN_BRIGHT", "OPEN_AUTO", "OPEN_AUTO"]
        )


class TestSensorErrorClose:
    """センサーエラー時でも閉める制御は実行されることのテスト (BUG-3)"""

    def test_schedule_ctrl_close_with_invalid_sensor(self, client, time_machine, mock_sensor_data):
        """センサー無効でもスケジュールされた閉める制御は実行される"""
        # 深夜に設定して自動制御が発動しないようにする
        setup_midnight_time(client, time_machine)

        sensor_data_mock = mock_sensor_data(SensorDataFactory.bright())

        shutter_api = ShutterAPI(client)
        schedule_api = ScheduleAPI(client)
        ctrl_checker = CtrlLogChecker(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        move_time_and_wait(time_machine, client, time_morning(0))

        # シャッターを開けておく
        shutter_api.open()

        # 閉めるスケジュールを設定（開けるは無効）
        schedule_data = ScheduleFactory.create(
            open_time=time_str(time_morning(1)),
            close_time=time_str(time_evening(1)),
            open_active=False,
        )
        schedule_api.update(schedule_data)
        wait_for_schedule_update_seq(client)

        ctrl_checker.wait_and_check(
            [
                {"index": 0, "state": "open"},
                {"index": 1, "state": "open"},
            ]
        )

        # センサーを無効にする
        sensor_data_mock.return_value = SensorDataFactory.invalid_lux()

        # 閉めるスケジュール時刻に移動
        move_time_and_wait(time_machine, client, time_evening(1))
        move_time_and_wait(time_machine, client, time_evening(2))

        # センサー無効でもスケジュールに従って閉まる
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
                "SCHEDULE",
                "CLOSE_SENSOR_UNKNOWN",
                "CLOSE_SCHEDULE",
                "CLOSE_SCHEDULE",
            ]
        )
        # センサー無効でも閉める動作はエラー通知しない
        slack_checker.check_no_error()
