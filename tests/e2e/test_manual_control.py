#!/usr/bin/env python3
"""手動シャッター制御のE2Eテスト"""

import time

import my_lib.time
from playwright.sync_api import Page

from tests.e2e.conftest import (
    advance_mock_time,
    clear_log,
    click_and_check_log,
    set_mock_time,
)


class TestManualControl:
    """手動シャッター制御のテスト"""

    def test_manual_open_close(self, page: Page, host: str, port: str) -> None:
        """手動でシャッターを開閉できる"""
        clear_log(page, host, port)

        # NOTE: モック時刻を初期設定（advance_mock_timeを使用するため）
        current_time = my_lib.time.now()
        set_mock_time(host, port, current_time)

        # NOTE: 連続してテスト実行する場合に open がはじかれないようにまず閉める
        click_and_check_log(page, host, port, "close-0", "手動で閉めました")
        click_and_check_log(page, host, port, "close-1", "手動で閉めました")
        time.sleep(5)

        # 手動操作間隔制限を回避するため時刻を進める
        advance_mock_time(host, port, 70)

        click_and_check_log(page, host, port, "open-0", "手動で開けました")
        # 手動操作間隔制限を回避するため時刻を進める
        advance_mock_time(host, port, 70)

        click_and_check_log(page, host, port, "open-1", "手動で開けました")
        # 手動操作間隔制限を回避するため時刻を進める
        advance_mock_time(host, port, 70)

        click_and_check_log(page, host, port, "close-0", "手動で閉めました")

        click_and_check_log(page, host, port, "close-0", "閉めるのを見合わせました")
        # 手動操作間隔制限を回避するため時刻を進める
        advance_mock_time(host, port, 70)

        click_and_check_log(page, host, port, "close-1", "手動で閉めました")
        # 手動操作間隔制限を回避するため時刻を進める
        advance_mock_time(host, port, 70)

        click_and_check_log(page, host, port, "open-0", "手動で開けました")

        click_and_check_log(page, host, port, "open-0", "開けるのを見合わせました")

        click_and_check_log(page, host, port, "open-1", "手動で開けました")

        # 手動操作間隔制限を回避するため時刻を進める
        advance_mock_time(host, port, 70)
        time.sleep(1)  # モック時間の変更が完全に反映されるまで追加待機

        click_and_check_log(page, host, port, "open-1", "手動で開けました")
