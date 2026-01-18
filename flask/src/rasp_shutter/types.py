#!/usr/bin/env python3
"""
rasp-shutter アプリケーション用の型定義

センサーデータやAPIレスポンスなどの構造を dataclass で明示的に定義します。
"""

import datetime
from dataclasses import dataclass, field
from typing import TypedDict


@dataclass
class SensorValue:
    """センサー値の型定義

    Attributes
    ----------
        valid: データが有効かどうか
        value: センサーの測定値（valid=True の場合のみ有効）
        time: 測定時刻（valid=True の場合のみ有効）

    """

    valid: bool
    value: float | None = None
    time: datetime.datetime | None = None

    @classmethod
    def create_valid(cls, value: float, time: datetime.datetime) -> "SensorValue":
        """有効なセンサー値を作成"""
        return cls(valid=True, value=value, time=time)

    @classmethod
    def create_invalid(cls) -> "SensorValue":
        """無効なセンサー値を作成"""
        return cls(valid=False)


@dataclass
class SensorData:
    """センサーデータ全体の型定義

    Attributes
    ----------
        lux: 照度センサーデータ
        solar_rad: 日射センサーデータ
        altitude: 太陽高度データ

    """

    lux: SensorValue
    solar_rad: SensorValue
    altitude: SensorValue


@dataclass
class ShutterStateEntry:
    """シャッター状態エントリの型定義

    Attributes
    ----------
        name: シャッター名
        state: シャッター状態（0=開、1=閉、2=不明）

    """

    name: str
    state: int


def state_to_action_text(state: str) -> str:
    """state ("open"/"close") を動作テキスト ("開け"/"閉め") に変換"""
    return "開け" if state == "open" else "閉め"


@dataclass
class ShutterStateResponse:
    """シャッター状態レスポンスの型定義

    Attributes
    ----------
        state: シャッター状態のリスト
        result: 処理結果

    """

    state: list[ShutterStateEntry] = field(default_factory=list)
    result: str = "success"


# ======================================================================
# スケジュール関連の型定義
# ======================================================================
class ScheduleEntry(TypedDict):
    """スケジュールエントリの型定義

    開く/閉じる制御のスケジュール設定を表します。

    Attributes
    ----------
        is_active: スケジュールが有効かどうか
        time: 実行時刻 (HH:MM形式)
        wday: 曜日ごとの有効フラグ [日, 月, 火, 水, 木, 金, 土]
        solar_rad: 日射閾値 (W/m^2)
        lux: 照度閾値 (LUX)
        altitude: 太陽高度閾値 (度)

    """

    is_active: bool
    time: str
    wday: list[bool]
    solar_rad: int
    lux: int
    altitude: int


class ScheduleData(TypedDict):
    """スケジュールデータ全体の型定義

    開く/閉じる両方のスケジュールを保持します。

    Attributes
    ----------
        open: 開く制御のスケジュール
        close: 閉じる制御のスケジュール

    """

    open: ScheduleEntry
    close: ScheduleEntry
