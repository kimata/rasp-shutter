#!/usr/bin/env python3
# ruff: noqa: S101
"""カスタムアサーション

ログ検証、Slack通知検証などのカスタムアサーションを提供します。
"""

import logging
import time
from typing import TYPE_CHECKING, ClassVar

import my_lib.notify.slack
import my_lib.pretty
import my_lib.webapp.config

from tests.helpers.time_utils import wait_until

if TYPE_CHECKING:
    from flask.testing import FlaskClient


class LogChecker:
    """アプリケーションログのチェッカー"""

    # ログメッセージとキーワードのマッピング
    LOG_PATTERNS: ClassVar[dict[str, str]] = {
        "OPEN_MANUAL": "手動で開けました",
        "OPEN_AUTO": "自動で開けました",
        "OPEN_FAIL": "開けるのに失敗しました",
        "OPEN_PENDING": "開けるのを見合わせました",
        "OPEN_BRIGHT": "明るくなってきたので開けます",
        "CLOSE_MANUAL": "手動で閉めました",
        "CLOSE_AUTO": "自動で閉めました",
        "CLOSE_SCHEDULE": "スケジューラで閉めました",
        "CLOSE_DARK": "暗くなってきたので閉めます",
        "CLOSE_PENDING": "閉めるのを見合わせました",
        "SCHEDULE": "スケジュールを更新",
        "INVALID": "スケジュールの指定が不正",
        "FAIL_SENSOR": "センサの値が不明",
        "FAIL_CONTROL": "制御に失敗しました",
        "CLEAR": "クリアされました",
    }

    def __init__(self, client: "FlaskClient"):
        self.client = client
        self.url_prefix = my_lib.webapp.config.URL_PREFIX

    def get_logs(self) -> list:
        """ログを取得

        Returns:
            ログエントリのリスト
        """
        response = self.client.get(f"{self.url_prefix}/api/log_view")
        if response.status_code in {200, 301}:
            result = response.json
            if result is not None:
                return result.get("data", [])
        return []

    def wait_and_check(
        self,
        expect_list: list[str],
        timeout_sec: float = 10.0,
        poll_interval_sec: float = 0.2,
    ) -> None:
        """ログが期待値になるまで待機してチェック

        Args:
            expect_list: 期待するログパターンのリスト（LOG_PATTERNSのキー）
            timeout_sec: タイムアウト秒数
            poll_interval_sec: ポーリング間隔秒数

        Raises:
            AssertionError: タイムアウトまたは検証失敗
        """
        start_time = time.time()

        # 期待するログ数が揃うまで待機
        while time.time() - start_time < timeout_sec:
            log_list = self.get_logs()
            if len(log_list) >= len(expect_list):
                break
            time.sleep(poll_interval_sec)

        log_list = self.get_logs()
        elapsed = time.time() - start_time

        assert len(log_list) == len(expect_list), (
            f"ログ数が期待値と異なります。期待: {len(expect_list)} 実際: {len(log_list)} "
            f"(待機時間: {elapsed:.1f}秒)\n{my_lib.pretty.format(log_list)}"
        )

        self._check_log_content(log_list, expect_list)

    def _check_log_content(self, log_list: list, expect_list: list[str]) -> None:
        """ログ内容をチェック

        Args:
            log_list: 実際のログリスト
            expect_list: 期待するログパターンのリスト

        Raises:
            AssertionError: 検証失敗
        """
        for i, expect in enumerate(reversed(expect_list)):
            if expect not in self.LOG_PATTERNS:
                msg = f"不明なログパターン: {expect}"
                raise AssertionError(msg)

            expected_message = self.LOG_PATTERNS[expect]
            actual_message = log_list[i].get("message", "")

            assert expected_message in actual_message, (
                f"ログ[{i}]が期待値と異なります。期待パターン: {expect} "
                f"('{expected_message}') 実際: '{actual_message}'"
            )


class CtrlLogChecker:
    """制御ログのチェッカー"""

    def __init__(self, client: "FlaskClient"):
        self.client = client
        self.url_prefix = my_lib.webapp.config.URL_PREFIX

    def get_logs(self) -> list:
        """制御ログを取得

        Returns:
            制御ログエントリのリスト
        """
        response = self.client.get(f"{self.url_prefix}/api/ctrl/log")
        result = response.json
        if response.status_code == 200 and result is not None and result.get("result") == "success":
            return result.get("log", [])
        return []

    def wait_and_check(
        self,
        expect: list[dict],
        timeout_sec: float = 10.0,
        poll_interval_sec: float = 0.5,
    ) -> None:
        """制御ログが期待値になるまで待機してチェック

        Args:
            expect: 期待する制御ログのリスト
            timeout_sec: タイムアウト秒数
            poll_interval_sec: ポーリング間隔秒数

        Raises:
            AssertionError: タイムアウトまたは検証失敗
        """
        start_time = time.time()

        while time.time() - start_time < timeout_sec:
            log_list = self.get_logs()
            if log_list == expect:
                return
            if len(log_list) >= len(expect):
                # ログ数が揃ったら内容をチェック
                break
            time.sleep(poll_interval_sec)

        log_list = self.get_logs()
        elapsed = time.time() - start_time

        logging.debug("Control log: %s", log_list)

        assert log_list == expect, (
            f"制御ログが期待値と異なります。(待機時間: {elapsed:.1f}秒)\n期待: {expect}\n実際: {log_list}"
        )

    def wait_for_count(
        self,
        min_count: int,
        timeout_sec: float = 10.0,
        poll_interval_sec: float = 0.5,
    ) -> list:
        """制御ログが指定数以上になるまで待機

        Args:
            min_count: 最小ログ数
            timeout_sec: タイムアウト秒数
            poll_interval_sec: ポーリング間隔秒数

        Returns:
            制御ログのリスト

        Raises:
            AssertionError: タイムアウト
        """
        success = wait_until(
            lambda: len(self.get_logs()) >= min_count,
            timeout_sec=timeout_sec,
            poll_interval_sec=poll_interval_sec,
        )

        log_list = self.get_logs()
        assert success, f"制御ログ数が不足。期待: {min_count}以上 実際: {len(log_list)}"
        return log_list


class SlackChecker:
    """Slack通知のチェッカー"""

    def check_notify(self, message: str | None, index: int = -1) -> None:
        """Slack通知をチェック

        Args:
            message: 期待するメッセージ（Noneの場合は通知がないことを確認）
            index: チェックする通知のインデックス（デフォルトは最新）

        Raises:
            AssertionError: 検証失敗
        """
        notify_hist = my_lib.notify.slack._hist_get(False)
        logging.debug("Slack notify history: %s", notify_hist)

        if message is None:
            assert notify_hist == [], "正常なはずなのに、エラー通知がされています。"
        else:
            assert len(notify_hist) != 0, "異常が発生したはずなのに、エラー通知がされていません。"
            assert message in notify_hist[index], f"「{message}」が Slack で通知されていません。"

    def check_no_error(self) -> None:
        """エラー通知がないことを確認

        Raises:
            AssertionError: エラー通知がある場合
        """
        self.check_notify(None)

    def check_error_contains(self, message: str) -> None:
        """エラー通知に指定メッセージが含まれることを確認

        Args:
            message: 期待するメッセージ

        Raises:
            AssertionError: 検証失敗
        """
        self.check_notify(message)

    def get_history(self) -> list:
        """通知履歴を取得

        Returns:
            通知履歴のリスト
        """
        return my_lib.notify.slack._hist_get(False)

    def clear(self) -> None:
        """通知履歴をクリア"""
        my_lib.notify.slack._hist_clear()
