#!/usr/bin/env python3
# ruff: noqa: S101
"""スケジュールAPIの統合テスト"""

import my_lib.pytest_util

import rasp_shutter.config
from tests.fixtures.schedule_factory import ScheduleFactory
from tests.helpers.api_utils import ScheduleAPI
from tests.helpers.assertions import LogChecker, SlackChecker
from tests.helpers.time_utils import setup_midnight_time


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
        schedule_path = rasp_shutter.config.get_environment().schedule_file_path
        if schedule_path is not None:
            # NOTE: my_lib.serializer は get_path() でワーカーサフィックスを付与して
            # 読み書きするため、実際に読まれるファイルに破損データを書き込む
            with my_lib.pytest_util.get_path(schedule_path).open(mode="wb") as f:
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
    """スケジュールバリデーションテスト

    NOTE: time_machineで深夜に設定し、センサーベースの自動制御が発動しないようにする。
    自動制御はHOUR_MORNING_START=5以降に実行されるため、3時に設定。
    setup_midnight_time()でスケジューラループ完了を待ってからログをクリア。
    """

    def test_schedule_ctrl_invalid_missing_open(self, client, time_machine):
        """openキーが欠けている場合"""
        setup_midnight_time(client, time_machine)

        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        del schedule_data["open"]
        schedule_api.update(schedule_data, expect_success=False)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_missing_is_active(self, client, time_machine):
        """is_activeキーが欠けている場合"""
        setup_midnight_time(client, time_machine)

        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        del schedule_data["open"]["is_active"]
        schedule_api.update(schedule_data, expect_success=False)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_is_active_type(self, client, time_machine):
        """is_activeの型が不正な場合"""
        setup_midnight_time(client, time_machine)

        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["is_active"] = "TEST"
        schedule_api.update(schedule_data, expect_success=False)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_lux_type(self, client, time_machine):
        """luxの型が不正な場合"""
        setup_midnight_time(client, time_machine)

        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["lux"] = "TEST"
        schedule_api.update(schedule_data, expect_success=False)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_solar_rad_type(self, client, time_machine):
        """solar_radの型が不正な場合"""
        setup_midnight_time(client, time_machine)

        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["solar_rad"] = "TEST"
        schedule_api.update(schedule_data, expect_success=False)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_time_format(self, client, time_machine):
        """timeの形式が不正な場合"""
        setup_midnight_time(client, time_machine)

        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["time"] = "TEST"
        schedule_api.update(schedule_data, expect_success=False)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_wday_length(self, client, time_machine):
        """wdayの長さが不正な場合"""
        setup_midnight_time(client, time_machine)

        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["wday"] = [True] * 5
        schedule_api.update(schedule_data, expect_success=False)

        log_checker.wait_and_check(["CLEAR", "INVALID"])

    def test_schedule_ctrl_invalid_wday_element_type(self, client, time_machine):
        """wdayの要素の型が不正な場合"""
        setup_midnight_time(client, time_machine)

        schedule_api = ScheduleAPI(client)
        log_checker = LogChecker(client)
        slack_checker = SlackChecker()

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["wday"] = ["TEST"] * 7
        schedule_api.update(schedule_data, expect_success=False)

        log_checker.wait_and_check(["CLEAR", "INVALID"])
        slack_checker.check_error_contains("スケジュールの指定が不正です。")

    def test_schedule_ctrl_invalid_json(self, client, time_machine):
        """data が JSON として壊れている場合は 400"""
        setup_midnight_time(client, time_machine)

        response = client.post(
            f"{rasp_shutter.config.URL_PREFIX}/api/schedule_ctrl",
            query_string={"cmd": "set", "data": "{broken json"},
        )
        assert response.status_code == 400
        assert response.json is not None
        assert response.json["result"] == "error"

    def test_schedule_ctrl_invalid_json_type(self, client, time_machine):
        """data が dict でない JSON の場合は 400"""
        setup_midnight_time(client, time_machine)

        response = client.post(
            f"{rasp_shutter.config.URL_PREFIX}/api/schedule_ctrl",
            query_string={"cmd": "set", "data": "[1, 2]"},
        )
        assert response.status_code == 400
        assert response.json is not None
        assert response.json["result"] == "error"

    def test_schedule_ctrl_invalid_key_name(self, client, time_machine):
        """キー名が open/close 以外の場合は 400"""
        setup_midnight_time(client, time_machine)

        schedule_api = ScheduleAPI(client)

        schedule_data = ScheduleFactory.create()
        schedule_data["foo"] = schedule_data.pop("close")
        schedule_api.update(schedule_data, expect_success=False)

    def test_schedule_ctrl_set_requires_post(self, client, time_machine):
        """cmd=set は GET では受け付けない（405）"""
        setup_midnight_time(client, time_machine)

        import json

        schedule_data = ScheduleFactory.create()
        response = client.get(
            f"{rasp_shutter.config.URL_PREFIX}/api/schedule_ctrl",
            query_string={"cmd": "set", "data": json.dumps(schedule_data)},
        )
        assert response.status_code == 405
        assert response.json is not None
        assert response.json["result"] == "error"

    def test_schedule_ctrl_validate_fail(self, client, mocker):
        """バリデーション失敗時の動作"""
        mocker.patch("rasp_shutter.control.scheduler.schedule_validate", return_value=False)

        schedule_api = ScheduleAPI(client)
        result = schedule_api.get()

        # デフォルト値が返される
        assert len(result) == 2
