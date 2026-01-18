#!/usr/bin/env python3
"""スケジュールデータファクトリー

テスト用のスケジュールデータを生成するファクトリークラスを提供します。
"""

import datetime
from typing import Any, ClassVar

import my_lib.time


class _Defaults:
    """デフォルト値を保持する内部クラス"""

    OPEN_TIME: str = "07:01"
    OPEN_SOLAR_RAD: int = 150
    OPEN_LUX: int = 1000
    OPEN_ALTITUDE: int = 10

    CLOSE_TIME: str = "17:01"
    CLOSE_SOLAR_RAD: int = 80
    CLOSE_LUX: int = 1200
    CLOSE_ALTITUDE: int = 15


class ScheduleFactory:
    """スケジュールデータ生成ファクトリー"""

    # デフォルト値への参照
    _defaults: ClassVar[type[_Defaults]] = _Defaults

    @classmethod
    def create(
        cls,
        open_time: str | None = None,
        close_time: str | None = None,
        open_active: bool = True,
        close_active: bool = True,
        open_solar_rad: int | None = None,
        close_solar_rad: int | None = None,
        open_lux: int | None = None,
        close_lux: int | None = None,
        open_altitude: int | None = None,
        close_altitude: int | None = None,
        wday: list[bool] | None = None,
    ) -> dict[str, Any]:
        """カスタムスケジュールデータを生成

        Args:
            open_time: 開ける時刻（HH:MM形式）
            close_time: 閉める時刻（HH:MM形式）
            open_active: 開けるスケジュールを有効にするか
            close_active: 閉めるスケジュールを有効にするか
            open_solar_rad: 開ける閾値（日射量）
            close_solar_rad: 閉める閾値（日射量）
            open_lux: 開ける閾値（照度）
            close_lux: 閉める閾値（照度）
            open_altitude: 開ける閾値（太陽高度）
            close_altitude: 閉める閾値（太陽高度）
            wday: 曜日設定（7要素のboolリスト、[日,月,火,水,木,金,土]）

        Returns:
            スケジュールデータ
        """
        if wday is None:
            wday = [True] * 7

        d = cls._defaults
        return {
            "open": {
                "is_active": open_active,
                "time": open_time if open_time is not None else d.OPEN_TIME,
                "solar_rad": open_solar_rad if open_solar_rad is not None else d.OPEN_SOLAR_RAD,
                "lux": open_lux if open_lux is not None else d.OPEN_LUX,
                "altitude": open_altitude if open_altitude is not None else d.OPEN_ALTITUDE,
                "wday": wday.copy(),
            },
            "close": {
                "is_active": close_active,
                "time": close_time if close_time is not None else d.CLOSE_TIME,
                "solar_rad": close_solar_rad if close_solar_rad is not None else d.CLOSE_SOLAR_RAD,
                "lux": close_lux if close_lux is not None else d.CLOSE_LUX,
                "altitude": close_altitude if close_altitude is not None else d.CLOSE_ALTITUDE,
                "wday": wday.copy(),
            },
        }

    @classmethod
    def at_time(
        cls,
        open_time: str,
        close_time: str,
        open_active: bool = True,
        close_active: bool = True,
    ) -> dict[str, Any]:
        """指定時刻のスケジュールを生成

        Args:
            open_time: 開ける時刻（HH:MM形式）
            close_time: 閉める時刻（HH:MM形式）
            open_active: 開けるスケジュールを有効にするか
            close_active: 閉めるスケジュールを有効にするか

        Returns:
            スケジュールデータ
        """
        return cls.create(
            open_time=open_time,
            close_time=close_time,
            open_active=open_active,
            close_active=close_active,
        )

    @classmethod
    def at_minutes_from_now(
        cls,
        open_offset_min: int = 1,
        close_offset_min: int = 60,
        open_active: bool = True,
        close_active: bool = True,
    ) -> dict[str, Any]:
        """現在時刻からの相対時刻でスケジュールを生成

        Args:
            open_offset_min: 開ける時刻のオフセット（分）
            close_offset_min: 閉める時刻のオフセット（分）
            open_active: 開けるスケジュールを有効にするか
            close_active: 閉めるスケジュールを有効にするか

        Returns:
            スケジュールデータ
        """
        now = my_lib.time.now()
        open_time = (now + datetime.timedelta(minutes=open_offset_min)).strftime("%H:%M")
        close_time = (now + datetime.timedelta(minutes=close_offset_min)).strftime("%H:%M")

        return cls.at_time(
            open_time=open_time,
            close_time=close_time,
            open_active=open_active,
            close_active=close_active,
        )

    @classmethod
    def inactive(cls) -> dict[str, Any]:
        """無効なスケジュールを生成

        Returns:
            両方無効なスケジュールデータ
        """
        return cls.create(open_active=False, close_active=False)

    @classmethod
    def open_only(
        cls,
        open_time: str | None = None,
    ) -> dict[str, Any]:
        """開けるのみ有効なスケジュールを生成

        Args:
            open_time: 開ける時刻（HH:MM形式）

        Returns:
            開けるのみ有効なスケジュールデータ
        """
        return cls.create(open_time=open_time, open_active=True, close_active=False)

    @classmethod
    def close_only(
        cls,
        close_time: str | None = None,
    ) -> dict[str, Any]:
        """閉めるのみ有効なスケジュールを生成

        Args:
            close_time: 閉める時刻（HH:MM形式）

        Returns:
            閉めるのみ有効なスケジュールデータ
        """
        return cls.create(open_active=False, close_active=True, close_time=close_time)

    @classmethod
    def weekday_only(cls) -> dict[str, Any]:
        """平日のみ有効なスケジュールを生成

        Returns:
            平日のみ有効なスケジュールデータ
        """
        # [日,月,火,水,木,金,土] - 月〜金のみ有効
        wday = [False, True, True, True, True, True, False]
        return cls.create(wday=wday)

    @classmethod
    def weekend_only(cls) -> dict[str, Any]:
        """週末のみ有効なスケジュールを生成

        Returns:
            週末のみ有効なスケジュールデータ
        """
        # [日,月,火,水,木,金,土] - 土日のみ有効
        wday = [True, False, False, False, False, False, True]
        return cls.create(wday=wday)

    @classmethod
    def no_weekday(cls) -> dict[str, Any]:
        """曜日が全て無効なスケジュールを生成

        Returns:
            曜日が全て無効なスケジュールデータ
        """
        return cls.create(wday=[False] * 7)


def time_morning(offset_min: int = 0) -> datetime.datetime:
    """朝の時刻（7:00 + オフセット分）を返す"""
    return my_lib.time.now().replace(hour=7, minute=0 + offset_min, second=0, microsecond=0)


def time_evening(offset_min: int = 0) -> datetime.datetime:
    """夕方の時刻（17:00 + オフセット分）を返す"""
    return my_lib.time.now().replace(hour=17, minute=0 + offset_min, second=0, microsecond=0)


def time_str(target_time: datetime.datetime) -> str:
    """時刻をHH:MM形式の文字列に変換"""
    return target_time.strftime("%H:%M")


def gen_schedule_data() -> dict[str, Any]:
    """後方互換性のためのスケジュールデータ生成関数"""
    return ScheduleFactory.create(
        open_time=time_str(time_morning(1)),
        close_time=time_str(time_evening(1)),
    )
