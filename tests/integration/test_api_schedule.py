#!/usr/bin/env python3
# ruff: noqa: S101
"""スケジュールAPIの統合テスト"""

import pathlib

import my_lib.webapp.config

from tests.fixtures.schedule_factory import ScheduleFactory
from tests.helpers.api_utils import ScheduleAPI
from tests.helpers.assertions import LogChecker, SlackChecker


class TestScheduleRead:
    """スケジュール読み取りテスト"""

    def test_schedule_ctrl_read(self, client):
        """スケジュールを読み取れる"""
        schedule_api = ScheduleAPI(client)

        result = schedule_api.get()

        assert len(result) == 2
        assert "open" in result
        assert "close" in result

    def test_schedule_ctrl_read_fail_missing_key(self, client, mocker):
        """キーが欠けているスケジュールの読み取り"""
        schedule_data = ScheduleFactory.create()
        del schedule_data["open"]

        mocker.patch("pickle.load", return_value=schedule_data)

        schedule_api = ScheduleAPI(client)
        result = schedule_api.get()

        # デフォルト値が返される
        assert len(result) == 2

    def test_schedule_ctrl_read_fail_corrupt_file(self, client):
        """破損したスケジュールファイルの読み取り"""
        schedule_path = my_lib.webapp.config.SCHEDULE_FILE_PATH
        if schedule_path is not None:
            with pathlib.Path(schedule_path).open(mode="wb") as f:
                f.write(b"TEST")

            schedule_api = ScheduleAPI(client)
            result = schedule_api.get()

            # デフォルト値が返される
            assert len(result) == 2


class TestScheduleUpdate:
    """スケジュール更新テスト"""

    def test_schedule_ctrl_update(self, client):
        """スケジュールを更新できる"""
        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create(
            open_time="08:30",
            close_time="18:30",
        )

        schedule_api.update(schedule_data)

        log_checker.wait_and_check(["CLEAR", "SCHEDULE"])

    def test_schedule_ctrl_write_fail(self, client, mocker):
        """スケジュール書き込み失敗"""
        mocker.patch("pickle.dump", side_effect=RuntimeError())

        schedule_api = ScheduleAPI(client)
        schedule_data = ScheduleFactory.create()
        schedule_api.update(schedule_data)

        # エラーが発生してもAPIは成功を返す
        # 次回のテストに向けて正常なものに戻す
        mocker.stopall()
        schedule_api.update(schedule_data)


class TestScheduleValidation:
    """スケジュールバリデーションテスト"""

    def test_schedule_ctrl_invalid_missing_open(self, client):
        """openキーが欠けている場合"""
        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        del schedule_data["open"]
        schedule_api.update(schedule_data)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_missing_is_active(self, client):
        """is_activeキーが欠けている場合"""
        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        del schedule_data["open"]["is_active"]
        schedule_api.update(schedule_data)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_is_active_type(self, client):
        """is_activeの型が不正な場合"""
        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["is_active"] = "TEST"
        schedule_api.update(schedule_data)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_lux_type(self, client):
        """luxの型が不正な場合"""
        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["lux"] = "TEST"
        schedule_api.update(schedule_data)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_solar_rad_type(self, client):
        """solar_radの型が不正な場合"""
        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["solar_rad"] = "TEST"
        schedule_api.update(schedule_data)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_time_format(self, client):
        """timeの形式が不正な場合"""
        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["time"] = "TEST"
        schedule_api.update(schedule_data)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_wday_length(self, client):
        """wdayの長さが不正な場合"""
        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["wday"] = [True] * 5
        schedule_api.update(schedule_data)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_wday_element_type(self, client):
        """wdayの要素の型が不正な場合"""
        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["wday"] = ["TEST"] * 7
        schedule_api.update(schedule_data)

        log_checker.wait_and_check(["CLEAR", "INVALID"])
        slack_checker.check_error_contains("スケジュールの指定が不正です。")

    def test_schedule_ctrl_validate_fail(self, client, mocker):
        """バリデーション失敗時の動作"""
        mocker.patch("rasp_shutter.control.scheduler.schedule_validate", return_value=False)

        schedule_api = ScheduleAPI(client)
        result = schedule_api.get()

        # デフォルト値が返される
        assert len(result) == 2
