#!/usr/bin/env python3
# ruff: noqa: S101
"""スケジューラーロジックのユニットテスト"""

from tests.fixtures.schedule_factory import ScheduleFactory


class TestScheduleValidate:
    """schedule_validate関数のテスト"""

    def test_validate_valid_schedule(self):
        """有効なスケジュールの検証"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is True

    def test_validate_missing_open(self):
        """openキーが欠けている場合"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        del schedule_data["open"]
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False

    def test_validate_missing_close(self):
        """closeキーが欠けている場合"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        del schedule_data["close"]
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False

    def test_validate_missing_is_active(self):
        """is_activeキーが欠けている場合"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        del schedule_data["open"]["is_active"]
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False

    def test_validate_missing_time(self):
        """timeキーが欠けている場合"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        del schedule_data["open"]["time"]
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False

    def test_validate_missing_wday(self):
        """wdayキーが欠けている場合"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        del schedule_data["open"]["wday"]
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False

    def test_validate_invalid_is_active_type(self):
        """is_activeの型が不正な場合"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["is_active"] = "true"  # stringは無効
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False

    def test_validate_invalid_lux_type(self):
        """luxの型が不正な場合"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["lux"] = "1000"  # stringは無効
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False

    def test_validate_invalid_solar_rad_type(self):
        """solar_radの型が不正な場合"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["solar_rad"] = "150"  # stringは無効
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False

    def test_validate_invalid_altitude_type(self):
        """altitudeの型が不正な場合"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["altitude"] = "10"  # stringは無効
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False

    def test_validate_invalid_time_format(self):
        """timeの形式が不正な場合"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["time"] = "7:00"  # HH:MM形式でない
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["time"] = "TEST"  # 不正な形式
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False

    def test_validate_invalid_wday_length(self):
        """wdayの長さが不正な場合"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["wday"] = [True] * 5  # 7要素でない
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False

    def test_validate_invalid_wday_element_type(self):
        """wdayの要素の型が不正な場合"""
        import rasp_shutter.control.scheduler

        schedule_data = ScheduleFactory.create()
        schedule_data["open"]["wday"] = ["True"] * 7  # boolでない
        assert rasp_shutter.control.scheduler.schedule_validate(schedule_data) is False


class TestGenScheduleDefault:
    """gen_schedule_default関数のテスト"""

    def test_default_schedule_structure(self):
        """デフォルトスケジュールの構造確認"""
        import rasp_shutter.control.scheduler

        default = rasp_shutter.control.scheduler.gen_schedule_default()

        assert "open" in default
        assert "close" in default

        for key in ["is_active", "time", "solar_rad", "lux", "altitude", "wday"]:
            assert key in default["open"]
            assert key in default["close"]

    def test_default_schedule_values(self):
        """デフォルトスケジュールの値確認"""
        import rasp_shutter.control.scheduler

        default = rasp_shutter.control.scheduler.gen_schedule_default()

        # デフォルトは無効
        assert default["open"]["is_active"] is False
        assert default["close"]["is_active"] is False

        # 時刻設定
        assert default["open"]["time"] == "08:00"
        assert default["close"]["time"] == "17:00"

        # 曜日は全て有効
        assert default["open"]["wday"] == [True] * 7
        assert default["close"]["wday"] == [True] * 7


class TestConvScheduleTimeToDatetime:
    """conv_schedule_time_to_datetime関数のテスト"""

    def test_convert_time_string(self):
        """時刻文字列からdatetimeへの変換"""
        import my_lib.time
        import rasp_shutter.control.scheduler

        result = rasp_shutter.control.scheduler.conv_schedule_time_to_datetime("08:30")

        assert result.hour == 8
        assert result.minute == 30
        assert result.day == my_lib.time.now().day
        assert result.tzinfo is not None

    def test_convert_midnight(self):
        """真夜中の時刻変換"""
        import rasp_shutter.control.scheduler

        result = rasp_shutter.control.scheduler.conv_schedule_time_to_datetime("00:00")

        assert result.hour == 0
        assert result.minute == 0

    def test_convert_end_of_day(self):
        """一日の終わりの時刻変換"""
        import rasp_shutter.control.scheduler

        result = rasp_shutter.control.scheduler.conv_schedule_time_to_datetime("23:59")

        assert result.hour == 23
        assert result.minute == 59


class TestGetScheduler:
    """get_scheduler関数のテスト"""

    def test_get_scheduler_returns_scheduler(self):
        """スケジューラーインスタンスを返すことを確認"""
        import rasp_shutter.control.scheduler
        import schedule

        scheduler = rasp_shutter.control.scheduler.get_scheduler()

        assert scheduler is not None
        assert isinstance(scheduler, schedule.Scheduler)

    def test_get_scheduler_same_instance(self):
        """同じワーカーでは同じインスタンスを返す"""
        import rasp_shutter.control.scheduler

        scheduler1 = rasp_shutter.control.scheduler.get_scheduler()
        scheduler2 = rasp_shutter.control.scheduler.get_scheduler()

        assert scheduler1 is scheduler2


class TestScheduleDataManagement:
    """スケジュールデータ管理のテスト"""

    def test_set_and_get_schedule_data(self):
        """スケジュールデータの設定と取得"""
        import rasp_shutter.control.scheduler

        test_data = ScheduleFactory.create()

        rasp_shutter.control.scheduler.set_schedule_data(test_data)
        result = rasp_shutter.control.scheduler.get_schedule_data()

        assert result == test_data

        # クリーンアップ
        rasp_shutter.control.scheduler.set_schedule_data(None)

    def test_get_schedule_data_returns_none_initially(self):
        """初期状態ではNoneを返す"""
        import os

        import rasp_shutter.control.scheduler

        # ワーカーIDを変更して新しいインスタンスを作成
        original_worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
        os.environ["PYTEST_XDIST_WORKER"] = "test_worker_unique"

        try:
            result = rasp_shutter.control.scheduler.get_schedule_data()
            assert result is None
        finally:
            os.environ["PYTEST_XDIST_WORKER"] = original_worker
