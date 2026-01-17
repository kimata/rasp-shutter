#!/usr/bin/env python3
"""時間関連のテストユーティリティ

time.sleepを削減するための待機ユーティリティを提供します。
"""

import datetime
import time
from collections.abc import Callable
from typing import TypeVar

import my_lib.time

T = TypeVar("T")


def wait_until(
    condition: Callable[[], bool],
    timeout_sec: float = 10.0,
    poll_interval_sec: float = 0.1,
    error_message: str | None = None,
) -> bool:
    """条件が満たされるまで待機

    Args:
        condition: 待機条件を返す関数（Trueになったら待機終了）
        timeout_sec: タイムアウト秒数
        poll_interval_sec: ポーリング間隔秒数
        error_message: タイムアウト時に表示するエラーメッセージ（Noneの場合はAssertErrorを投げない）

    Returns:
        条件が満たされたらTrue、タイムアウトしたらFalse
    """
    start = time.time()
    while time.time() - start < timeout_sec:
        if condition():
            return True
        time.sleep(poll_interval_sec)

    if error_message is not None:
        msg = f"Timeout after {timeout_sec}s: {error_message}"
        raise AssertionError(msg)

    return False


def wait_until_value(
    getter: Callable[[], T],
    expected: T,
    timeout_sec: float = 10.0,
    poll_interval_sec: float = 0.1,
) -> bool:
    """値が期待値になるまで待機

    Args:
        getter: 値を取得する関数
        expected: 期待する値
        timeout_sec: タイムアウト秒数
        poll_interval_sec: ポーリング間隔秒数

    Returns:
        期待値になったらTrue、タイムアウトしたらFalse
    """
    return wait_until(
        lambda: getter() == expected,
        timeout_sec=timeout_sec,
        poll_interval_sec=poll_interval_sec,
    )


def wait_until_count(
    getter: Callable[[], list | int],
    min_count: int,
    timeout_sec: float = 10.0,
    poll_interval_sec: float = 0.1,
) -> bool:
    """リストの要素数または整数が指定数以上になるまで待機

    Args:
        getter: リストまたは整数を取得する関数
        min_count: 最小要素数
        timeout_sec: タイムアウト秒数
        poll_interval_sec: ポーリング間隔秒数

    Returns:
        条件を満たしたらTrue、タイムアウトしたらFalse
    """

    def check_count():
        result = getter()
        if isinstance(result, int):
            return result >= min_count
        return len(result) >= min_count

    return wait_until(
        check_count,
        timeout_sec=timeout_sec,
        poll_interval_sec=poll_interval_sec,
    )


def time_morning(offset_min: int = 0) -> datetime.datetime:
    """朝の時刻（7:00 + オフセット分）を返す

    Args:
        offset_min: 7:00からのオフセット分

    Returns:
        設定された時刻のdatetime
    """
    return my_lib.time.now().replace(hour=7, minute=0 + offset_min, second=0, microsecond=0)


def time_evening(offset_min: int = 0) -> datetime.datetime:
    """夕方の時刻（17:00 + オフセット分）を返す

    Args:
        offset_min: 17:00からのオフセット分

    Returns:
        設定された時刻のdatetime
    """
    return my_lib.time.now().replace(hour=17, minute=0 + offset_min, second=0, microsecond=0)


def time_str(target_time: datetime.datetime) -> str:
    """時刻をHH:MM形式の文字列に変換

    Args:
        target_time: 変換する時刻

    Returns:
        HH:MM形式の文字列
    """
    return target_time.strftime("%H:%M")


def move_to(time_machine, target_time: datetime.datetime) -> None:
    """time_machineを使用して指定時刻に移動

    Args:
        time_machine: pytest-time-machineのfixture
        target_time: 移動先の時刻
    """
    time_machine.move_to(target_time)


def wait_for_scheduler(
    timeout_sec: float = 5.0,
    pre_wait_sec: float = 2.0,
    post_wait_sec: float = 0.5,
) -> bool:
    """スケジューラーの自動制御完了を待機

    NOTE: rasp_shutter.control.schedulerはmy_lib.webapp.configが
    初期化された後にインポートする必要があるため、この関数内でインポートする

    Args:
        timeout_sec: タイムアウト秒数
        pre_wait_sec: イベント待機前の待機秒数（スケジューラーが時間変更を検出するため）
        post_wait_sec: イベント待機後の追加待機秒数（スケジューラースレッド処理完了用）

    Returns:
        完了したらTrue
    """
    import rasp_shutter.control.scheduler

    # スケジューラースレッドが時間変更を検出して run_pending() を呼ぶまで待機
    # スケジューラーは0.5秒間隔でループするため、最低1秒待機する
    time.sleep(pre_wait_sec)

    result = rasp_shutter.control.scheduler.wait_for_auto_control_completion(timeout_sec)
    # スケジューラースレッドが処理を完了するための追加待機
    time.sleep(post_wait_sec)
    return result


def wait_for_schedule_update(wait_sec: float = 2.0) -> None:
    """スケジュール更新後にスケジューラーがキューを処理するまで待機

    スケジュールライブラリは現在時刻以降の次回実行時刻を計算するため、
    スケジュール更新後、予定時刻に移動する前に待機する必要がある。

    Args:
        wait_sec: 待機秒数（スケジューラーは0.5秒間隔でループ）
    """
    time.sleep(wait_sec)
