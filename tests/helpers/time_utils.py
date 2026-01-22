#!/usr/bin/env python3
"""時間関連のテストユーティリティ

time.sleepを削減するための待機ユーティリティを提供します。
"""

import datetime
import time
import warnings
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

import my_lib.time
import my_lib.webapp.config

if TYPE_CHECKING:
    from flask.testing import FlaskClient

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
    # NOTE: time.perf_counter() を使用（time_machine の影響を受けない）
    start = time.perf_counter()
    while time.perf_counter() - start < timeout_sec:
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


def get_scheduler_sequence(client: "FlaskClient") -> int:
    """スケジューラの現在のループシーケンス番号を取得

    Args:
        client: Flaskテストクライアント

    Returns:
        現在のシーケンス番号
    """
    response = client.get(f"{my_lib.webapp.config.URL_PREFIX}/api/test/scheduler/loop_sequence")
    assert response.status_code == 200  # noqa: S101
    data = response.get_json()
    assert data is not None  # noqa: S101
    return data.get("sequence", 0)


def wait_for_scheduler_loop(
    client: "FlaskClient",
    sequence: int,
    timeout: float = 10.0,
) -> bool:
    """スケジューラのループ完了を待機

    NOTE: サーバー側でブロッキング待機を行うとFlaskテストクライアントの
    シングルスレッド動作により問題が発生するため、クライアント側でポーリングを行う。

    Args:
        client: Flaskテストクライアント
        sequence: 待機開始時のシーケンス番号
        timeout: タイムアウト秒数

    Returns:
        成功したら True
    """
    # NOTE: スケジューラループは0.1秒間隔で動作するため、ポーリング間隔は
    # 0.2秒に設定してレイテンシを最小化しつつ、過度なCPU負荷を避ける。
    poll_interval = 0.2  # 200ms間隔でポーリング
    start = time.perf_counter()  # time_machineの影響を受けない

    while time.perf_counter() - start < timeout:
        current_seq = get_scheduler_sequence(client)
        if current_seq > sequence:
            return True
        time.sleep(poll_interval)

    return get_scheduler_sequence(client) > sequence


def move_time_and_wait(
    time_machine,  # type: ignore[no-untyped-def]
    client: "FlaskClient",
    target_time: datetime.datetime,
    timeout: float = 180.0,
) -> bool:
    """指定時刻に移動してスケジューラのループ完了を待機

    time_machine で時間を移動した後、スケジューラが少なくとも
    2回ループを完了するまで待機する。

    NOTE: 時間移動前にスケジューラループが実行中の場合、そのループは
    古い時刻で処理される可能性がある。確実に新しい時刻でのループを待つため、
    2回のループ完了を待機する。

    NOTE: 高並列環境（16+ワーカー）ではCPU競合によりスケジューラスレッドの
    実行が大幅に遅延する可能性があるため、十分なタイムアウトを設定する。

    Args:
        time_machine: pytest-time-machine の fixture
        client: Flaskテストクライアント
        target_time: 移動先の時刻
        timeout: タイムアウト秒数（デフォルト180秒、高並列環境対応）

    Returns:
        成功したら True

    Raises:
        AssertionError: タイムアウトした場合
    """
    # 時間を移動
    time_machine.move_to(target_time)

    # 2回ループを待機することで、時間移動後のループを確実に含む
    # 1回目: 移動前から実行中だったループ（または直後に開始したループ）
    # 2回目: 確実に新しい時刻を認識したループ
    half_timeout = timeout / 2
    for i in range(2):
        sequence = get_scheduler_sequence(client)
        result = wait_for_scheduler_loop(client, sequence, half_timeout)
        if not result:
            current_seq = get_scheduler_sequence(client)

            # デバッグ: タイムアウト時にスケジューラスレッドの状態を確認
            import sys
            import threading
            import traceback

            thread_info = []
            for thread in threading.enumerate():
                if "schedule" in thread.name.lower():
                    thread_info.append(f"{thread.name}: alive={thread.is_alive()}, daemon={thread.daemon}")
                    # スレッドのスタックトレースを取得
                    for thread_id, frame in sys._current_frames().items():
                        if thread.ident == thread_id:
                            stack = "".join(traceback.format_stack(frame))
                            thread_info.append(f"  Stack:\n{stack}")
                            break

            msg = (
                f"Scheduler loop {i + 1}/2 timed out after {half_timeout}s "
                f"(start_sequence={sequence}, current_sequence={current_seq}, target={target_time})\n"
                f"Scheduler threads: {thread_info}"
            )
            raise AssertionError(msg)

    return True


def wait_for_scheduler(
    timeout_sec: float = 5.0,
    pre_wait_sec: float = 2.0,
    post_wait_sec: float = 0.5,
) -> bool:
    """スケジューラーの自動制御完了を待機

    .. deprecated::
        move_time_and_wait() を使用してください。
        固定時間待機はCPU負荷が高い環境で不安定になる可能性があります。

    NOTE: rasp_shutter.control.schedulerはmy_lib.webapp.configが
    初期化された後にインポートする必要があるため、この関数内でインポートする

    Args:
        timeout_sec: タイムアウト秒数
        pre_wait_sec: イベント待機前の待機秒数（スケジューラーが時間変更を検出するため）
        post_wait_sec: イベント待機後の追加待機秒数（スケジューラースレッド処理完了用）

    Returns:
        完了したらTrue
    """
    warnings.warn(
        "wait_for_scheduler() is deprecated. Use move_time_and_wait() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    import rasp_shutter.control.scheduler

    # スケジューラースレッドが時間変更を検出して run_pending() を呼ぶまで待機
    # スケジューラーは0.5秒間隔でループするため、最低1秒待機する
    time.sleep(pre_wait_sec)

    result = rasp_shutter.control.scheduler.wait_for_auto_control_completion(timeout_sec)
    # スケジューラースレッドが処理を完了するための追加待機
    time.sleep(post_wait_sec)
    return result


def wait_for_schedule_update_seq(client: "FlaskClient", timeout: float = 60.0) -> bool:
    """スケジュール更新後にスケジューラーがキューを処理するまで待機（シーケンスベース）

    スケジュールライブラリは現在時刻以降の次回実行時刻を計算するため、
    スケジュール更新後、予定時刻に移動する前に待機する必要がある。

    Args:
        client: Flaskテストクライアント
        timeout: タイムアウト秒数（デフォルト60秒、高並列環境対応）

    Returns:
        成功したら True

    Raises:
        AssertionError: タイムアウトした場合
    """
    sequence = get_scheduler_sequence(client)
    result = wait_for_scheduler_loop(client, sequence, timeout)
    assert result, f"Schedule update wait timed out after {timeout}s (sequence={sequence})"
    return result


def wait_for_schedule_update(wait_sec: float = 2.0) -> None:
    """スケジュール更新後にスケジューラーがキューを処理するまで待機

    スケジュールライブラリは現在時刻以降の次回実行時刻を計算するため、
    スケジュール更新後、予定時刻に移動する前に待機する必要がある。

    Args:
        wait_sec: 待機秒数（スケジューラーは0.5秒間隔でループ）
    """
    time.sleep(wait_sec)


def get_midnight_time() -> datetime.datetime:
    """自動制御が発動しない深夜時刻を取得

    自動制御は HOUR_MORNING_START=5 以降に実行されるため、
    3時に設定することで自動制御が発動しないようにする。

    Returns:
        深夜3時の datetime
    """
    return my_lib.time.now().replace(hour=3, minute=0, second=0, microsecond=0)


def setup_midnight_time(
    client: "FlaskClient",
    time_machine,  # type: ignore[no-untyped-def]
    clear_ctrl_log: bool = True,
    timeout: float = 30.0,
) -> None:
    """深夜時刻に設定し、スケジューラループを待機してからログをクリア

    自動制御が発動しない深夜時刻（HOUR_MORNING_START=5より前の3時）に
    時刻を設定し、スケジューラがループを完了するまで待機する。

    並列テスト実行時にテスト間の干渉を防ぐため、各テストの開始時に
    呼び出すことを推奨。

    Args:
        client: Flaskテストクライアント
        time_machine: pytest-time-machine の fixture
        clear_ctrl_log: 制御ログをクリアするかどうか（デフォルト: True）
        timeout: スケジューラ待機のタイムアウト秒数
    """
    # NOTE: 関数内でインポート（循環インポート回避）
    from tests.helpers.api_utils import CtrlLogAPI

    sequence = get_scheduler_sequence(client)
    time_machine.move_to(get_midnight_time())
    wait_for_scheduler_loop(client, sequence, timeout=timeout)

    # ログをクリア
    client.get(f"{my_lib.webapp.config.URL_PREFIX}/api/log_clear")
    if clear_ctrl_log:
        CtrlLogAPI(client).clear()

    # クリアログが反映されるまで少し待機
    time.sleep(0.2)
