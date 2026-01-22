#!/usr/bin/env python3
"""E2Eテスト用Playwright固有fixture"""

import datetime
import logging
import random
import time
from typing import Any

import my_lib.time
import pytest
import requests
from playwright.sync_api import Page, expect

APP_URL_TMPL = "http://{host}:{port}/rasp-shutter/"

# urllib3のconnectionpoolログを抑制
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)


def app_url(host: str, port: str) -> str:
    """アプリケーションURLを生成"""
    return APP_URL_TMPL.format(host=host, port=port)


def wait_for_server_ready(host: str, port: str, timeout_sec: int = 30) -> None:
    """サーバーが起動するまで待機"""
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        try:
            res = requests.get(app_url(host, port), timeout=5)
            if res.ok:
                logging.info("サーバが %.1f 秒後に起動しました。", time.time() - start_time)
                return
        except Exception:  # noqa: S110
            pass
        time.sleep(1)

    raise RuntimeError(f"サーバーが {timeout_sec}秒以内に起動しませんでした。")


def set_mock_time(host: str, port: str, target_time: datetime.datetime) -> bool:
    """テスト用APIを使用してモック時刻を設定"""
    logging.info("set server time: %s", target_time)

    api_url = APP_URL_TMPL.format(host=host, port=port) + f"api/test/time/set/{target_time.isoformat()}"

    try:
        response = requests.post(api_url, timeout=5)
        logging.info("API response status: %d", response.status_code)
        if response.status_code == 200:
            response_data = response.json()
            logging.info("server mock time set to: %s", response_data["mock_time"])
            return True
        else:
            logging.error("API request failed with status %d: %s", response.status_code, response.text)
        return False
    except requests.RequestException:
        logging.exception("API request exception")
        return False


def advance_mock_time(host: str, port: str, seconds: int) -> bool:
    """テスト用APIを使用してモック時刻を進める"""
    logging.info("advance server time: %d sec", seconds)

    api_url = APP_URL_TMPL.format(host=host, port=port) + f"api/test/time/advance/{seconds}"

    try:
        response = requests.post(api_url, timeout=5)

        if response.status_code == 200:
            try:
                response_data = response.json()
                logging.info("API response data: %s", response_data)
                if "mock_time" in response_data:
                    logging.info("server mock time advanced to: %s", response_data["mock_time"])
                else:
                    logging.warning("mock_time field not found in response: %s", response_data)
            except Exception as e:
                logging.warning("Failed to parse JSON response: %s, content: %s", e, response.text)
            # モック時間の変更がアプリケーション全体に反映されるまで待機
            time.sleep(0.5)
            return True
        else:
            logging.error("API request failed with status %d: %s", response.status_code, response.text)
        return False
    except requests.RequestException:
        logging.exception("API request exception")
        return False


def reset_mock_time(host: str, port: str) -> bool:
    """テスト用APIを使用してモック時刻をリセット"""
    logging.info("reset server time")

    api_url = APP_URL_TMPL.format(host=host, port=port) + "api/test/time/reset"
    try:
        response = requests.post(api_url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def get_current_server_time(host: str, port: str) -> datetime.datetime | None:
    """テスト用APIを使用してサーバーの現在時刻を取得"""
    api_url = APP_URL_TMPL.format(host=host, port=port) + "api/test/time/current"
    try:
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            time_data = response.json()
            current_time = datetime.datetime.fromisoformat(time_data["current_time"])
            logging.info("server time: %s", current_time)
            return current_time
        return None
    except requests.RequestException:
        return None


def clear_control_history(host: str, port: str) -> bool:
    """テスト用APIを使用して制御履歴をクリア"""
    api_url = APP_URL_TMPL.format(host=host, port=port) + "api/ctrl/clear"
    try:
        response = requests.post(api_url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def reset_test_state(host: str, port: str) -> bool:
    """テスト用APIを使用してテスト状態をリセット"""
    api_url = APP_URL_TMPL.format(host=host, port=port) + "api/test/state/reset"
    try:
        response = requests.post(api_url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def clear_log(page: Page, host: str, port: str) -> None:
    """ログをクリア"""
    page.goto(app_url(host, port), wait_until="domcontentloaded", timeout=30000)

    page.get_by_test_id("clear").click()
    time.sleep(5)
    check_log(page, "ログがクリアされました")


def get_log_count(page: Page) -> int:
    """現在のログ数を取得"""
    return page.locator('//div[contains(@class,"log")]/div/div[2]').count()


def wait_for_log(
    page: Page,
    expected_text: str,
    timeout_sec: float = 30.0,
    poll_interval_sec: float = 1.0,
) -> bool:
    """ログに指定テキストが現れるまでポーリング待機

    Args:
        page: Playwrightページオブジェクト
        expected_text: 期待するログテキスト
        timeout_sec: タイムアウト秒数
        poll_interval_sec: ポーリング間隔秒数

    Returns:
        True: ログが見つかった, False: タイムアウト

    """
    log_locator = page.locator('//div[contains(@class,"log")]/div/div[2]')
    start = time.time()
    while time.time() - start < timeout_sec:
        # 全ログエントリをチェック
        for i in range(log_locator.count()):
            if expected_text in log_locator.nth(i).inner_text():
                return True
        time.sleep(poll_interval_sec)
    return False


def check_log(
    page: Page,
    message: str,
    timeout_sec: int = 10,
    initial_log_count: int | None = None,
) -> None:
    """
    最初のログメッセージ（最新ログ）が期待する内容かを確認する

    Args:
        page: Playwrightページオブジェクト
        message: 期待するログメッセージ
        timeout_sec: タイムアウト秒数
        initial_log_count: 操作前のログ数（指定された場合は新しいログの追加を待機）

    """
    log_locator = page.locator('//div[contains(@class,"log")]/div/div[2]')

    if initial_log_count is None:
        time.sleep(5)
    else:
        # 新しいログが追加されるまで最大5秒間待機
        start_time = time.time()
        while time.time() - start_time < 5:
            current_count = log_locator.count()
            if current_count > initial_log_count:
                break
            time.sleep(0.1)

        # さらに短時間待機してDOMの更新を確実にする
        time.sleep(0.5)

    # 最初のログ（最新ログ）が期待するメッセージを含むかチェック
    expect(log_locator.first).to_contain_text(message, timeout=timeout_sec * 1000)

    # NOTE: ログクリアする場合、ログの内容が変化しているので、ここで再取得する
    log_list = page.locator('//div[contains(@class,"log")]/div/div[2]')
    for i in range(log_list.count()):
        expect(log_list.nth(i)).not_to_contain_text("失敗")
        expect(log_list.nth(i)).not_to_contain_text("エラー")


def click_and_check_log(
    page: Page,
    host: str,
    port: str,
    test_id: str,
    expected_message: str,
    timeout_sec: int = 10,
) -> None:
    """
    要素をクリックして新しいログメッセージを確認する

    Args:
        page: Playwrightページオブジェクト
        host: サーバーホスト名
        port: サーバーポート番号
        test_id: クリックする要素のtest-id
        expected_message: 期待するログメッセージ
        timeout_sec: タイムアウト秒数

    """
    initial_count = get_log_count(page)
    get_current_server_time(host, port)
    logging.info("Click %s", test_id)
    page.get_by_test_id(test_id).click()
    check_log(page, expected_message, timeout_sec=timeout_sec, initial_log_count=initial_count)


def time_str_random() -> str:
    """ランダムな時刻文字列を生成"""
    return f"{int(24 * random.random()):02d}:{int(60 * random.random()):02d}"  # noqa: S311


def time_str_after(min_value: int) -> str:
    """現在時刻から指定分後の時刻文字列を取得"""
    return (my_lib.time.now() + datetime.timedelta(minutes=min_value)).strftime("%H:%M")


def number_random(min_value: int, max_value: int) -> str:
    """ランダムな数値文字列を生成"""
    return str(int(min_value + (max_value - min_value) * random.random()))  # noqa: S311


def bool_random() -> bool:
    """ランダムなブール値を生成"""
    return random.random() >= 0.5  # noqa: S311


def check_schedule(
    page: Page,
    enable_schedule_index: int,
    schedule_time: list[str],
    solar_rad: list[str],
    lux: list[str],
    enable_wday_index: list[bool],
) -> None:
    """スケジュール設定を確認"""
    enable_checkbox = page.locator('//input[contains(@id,"-schedule-entry")]')

    for i, state in enumerate(["open", "close"]):
        if i == enable_schedule_index:
            expect(enable_checkbox.nth(i)).to_be_checked()
        else:
            expect(enable_checkbox.nth(i)).not_to_be_checked()

        expect(page.locator(f'//div[contains(@id,"{state}-schedule-entry-time")]/input')).to_have_value(
            schedule_time[i]
        )

        expect(page.locator(f'//div[contains(@id,"{state}-schedule-entry-solar_rad")]/input')).to_have_value(
            solar_rad[i]
        )

        expect(page.locator(f'//div[contains(@id,"{state}-schedule-entry-lux")]/input')).to_have_value(lux[i])

        wday_checkbox = page.locator(f'//div[contains(@id,"{state}-schedule-entry-wday")]/span/input')
        for j in range(7):
            if enable_wday_index[i * 7 + j]:
                expect(wday_checkbox.nth(j)).to_be_checked()
            else:
                expect(wday_checkbox.nth(j)).not_to_be_checked()


@pytest.fixture(autouse=True)
def _server_init(page: Page, host: str, port: str, webserver: Any) -> None:
    """サーバー初期化fixture"""
    # If webserver fixture was not used (server not auto-started), wait for manual server
    if webserver is None:
        wait_for_server_ready(host, port)

    time.sleep(5)

    page.on("console", lambda msg: print(msg.text))
    page.set_viewport_size({"width": 2400, "height": 1600})

    # 各テスト前にモック時間をリセットして実時間に戻す
    # これにより前のテストの時間設定が影響しない
    reset_mock_time(host, port)

    clear_control_history(host, port)
