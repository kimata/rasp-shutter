#!/usr/bin/env python3
# ruff: noqa: S101

import datetime
import logging
import random
import time

import my_lib.time
import my_lib.webapp.config
import pytest
import requests
from playwright.sync_api import expect

APP_URL_TMPL = "http://{host}:{port}/rasp-shutter/"

SCHEDULE_AFTER_MIN = 1

# urllib3のconnectionpoolログを抑制
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)


@pytest.fixture(autouse=True)
def _server_init(page, host, port):
    wait_for_server_ready(host, port)

    time.sleep(10)

    page.on("console", lambda msg: print(msg.text))  # noqa: T201
    page.set_viewport_size({"width": 2400, "height": 1600})

    clear_control_history(host, port)


def wait_for_server_ready(host, port):
    TIMEOUT_SEC = 180

    start_time = time.time()
    while time.time() - start_time < TIMEOUT_SEC:
        try:
            res = requests.get(f"http://{host}:{port}")  # noqa: S113
            if res.ok:
                logging.info("サーバが %.1f 秒後に起動しました。", time.time() - start_time)
                return
        except Exception:  # noqa: S110
            pass
        time.sleep(1)

    raise RuntimeError(f"サーバーが {TIMEOUT_SEC}秒以内に起動しませんでした。")  # noqa: TRY003, EM102


def check_log(page, message, timeout_sec=5):
    expect(page.locator('//div[contains(@class,"log")]/div/div[2]').first).to_contain_text(
        message, timeout=timeout_sec * 1000
    )

    # NOTE: ログクリアする場合、ログの内容が変化しているので、ここで再取得する
    log_list = page.locator('//div[contains(@class,"log")]/div/div[2]')
    for i in range(log_list.count()):
        expect(log_list.nth(i)).not_to_contain_text("失敗")
        expect(log_list.nth(i)).not_to_contain_text("エラー")


def time_str_random():
    return f"{int(24 * random.random()):02d}:{int(60 * random.random()):02d}"  # noqa: S311


def time_str_after(min_value):
    return (my_lib.time.now() + datetime.timedelta(minutes=min_value)).strftime("%H:%M")


def number_random(min_value, max_value):
    return str(int(min_value + (max_value - min_value) * random.random()))  # noqa: S311


def bool_random():
    return random.random() >= 0.5  # noqa: S311


def check_schedule(page, enable_schedule_index, schedule_time, solar_rad, lux, enable_wday_index):  # noqa: PLR0913
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


def app_url(server, port):
    return APP_URL_TMPL.format(host=server, port=port)


def set_mock_time(host, port, target_time):
    """テスト用APIを使用してモック時刻を設定"""
    logging.info("set server time: %s", target_time)

    api_url = APP_URL_TMPL.format(host=host, port=port) + f"api/test/time/set/{target_time.isoformat()}"
    try:
        response = requests.post(api_url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def advance_mock_time(host, port, seconds):
    """テスト用APIを使用してモック時刻を進める"""
    logging.info("advance server time: %d sec", seconds)

    api_url = APP_URL_TMPL.format(host=host, port=port) + f"api/test/time/advance/{seconds}"
    try:
        response = requests.post(api_url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def reset_mock_time(host, port):
    """テスト用APIを使用してモック時刻をリセット"""
    logging.info("reset server time")

    api_url = APP_URL_TMPL.format(host=host, port=port) + "api/test/time/reset"
    try:
        response = requests.post(api_url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def get_current_server_time(host, port):
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


def clear_control_history(host, port):
    """テスト用APIを使用して制御履歴をクリア"""
    api_url = APP_URL_TMPL.format(host=host, port=port) + "api/ctrl/clear"
    try:
        response = requests.post(api_url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


######################################################################
def test_time():
    import schedule

    logging.debug("datetime.now()                        = %s", datetime.datetime.now())  # noqa: DTZ005
    logging.debug(
        "datetime.now(%10s)              = %s",
        my_lib.time.get_tz(),
        datetime.datetime.now(my_lib.time.get_zoneinfo()),
    )
    logging.debug(
        "datetime.now().replace(...)           = %s",
        datetime.datetime.now().replace(hour=0, minute=0, second=0),  # noqa: DTZ005
    )
    logging.debug(
        "datetime.now(%10s).replace(...) = %s",
        my_lib.time.get_tz(),
        my_lib.time.now().replace(hour=0, minute=0, second=0),
    )

    schedule.clear()
    job_time_str = time_str_after(SCHEDULE_AFTER_MIN)
    logging.debug("set schedule at %s", job_time_str)
    job = schedule.every().day.at(job_time_str, my_lib.time.get_pytz()).do(lambda: True)

    idle_sec = schedule.idle_seconds()
    logging.debug("Time to next jobs is %.1f sec", idle_sec)
    logging.debug("Next run is %s", job.next_run)

    assert idle_sec < 60


def test_manual(page, host, port):
    page.goto(app_url(host, port), wait_until="domcontentloaded", timeout=30000)

    page.get_by_test_id("clear").click()
    time.sleep(3)  # Wait for log processing
    check_log(page, "ログがクリアされました")

    # NOTE: 連続してテスト実行する場合に open がはじかれないようにまず閉める
    page.get_by_test_id("close-0").click()
    check_log(page, "手動で閉めました")
    # 手動操作間隔制限を回避するため時刻を進める
    advance_mock_time(host, port, 70)

    page.get_by_test_id("open-0").click()
    check_log(page, "手動で開けました")
    # 手動操作間隔制限を回避するため時刻を進める
    advance_mock_time(host, port, 70)

    page.get_by_test_id("open-1").click()
    check_log(page, "手動で開けました")
    # 手動操作間隔制限を回避するため時刻を進める
    advance_mock_time(host, port, 70)

    page.get_by_test_id("close-0").click()
    check_log(page, "手動で閉めました")

    page.get_by_test_id("close-0").click()
    check_log(page, "閉めるのを見合わせました")
    # 手動操作間隔制限を回避するため時刻を進める
    advance_mock_time(host, port, 70)

    page.get_by_test_id("close-1").click()
    check_log(page, "手動で閉めました")
    # 手動操作間隔制限を回避するため時刻を進める
    advance_mock_time(host, port, 70)

    page.get_by_test_id("open-0").click()
    check_log(page, "手動で開けました")

    page.get_by_test_id("open-0").click()
    check_log(page, "開けるのを見合わせました")

    page.get_by_test_id("open-1").click()
    check_log(page, "手動で開けました")
    # 手動操作間隔制限を回避するため時刻を進める
    advance_mock_time(host, port, 70)

    page.get_by_test_id("open-1").click()
    check_log(page, "手動で開けました")


def test_schedule(page, host, port):
    page.goto(app_url(host, port), wait_until="domcontentloaded", timeout=30000)

    page.get_by_test_id("clear").click()
    time.sleep(3)  # Wait longer for log processing
    check_log(page, "ログがクリアされました")

    # NOTE: ランダムなスケジュール設定を準備
    schedule_time = [time_str_random(), time_str_random()]
    solar_rad = [number_random(100, 200), number_random(100, 200)]
    lux = [number_random(500, 2000), number_random(500, 2000)]
    enable_wday_index = [bool_random() for _ in range(14)]
    enable_schedule_index = int(2 * random.random())  # noqa: S311
    enable_checkbox = page.locator('//input[contains(@id,"-schedule-entry")]')
    for i, state in enumerate(["open", "close"]):
        # NTE: 最初に強制的に有効にしておく
        enable_checkbox.nth(i).evaluate("node => node.checked = false")
        enable_checkbox.nth(i).evaluate("node => node.click()")

        page.locator(f'//div[contains(@id,"{state}-schedule-entry-time")]/input').fill(schedule_time[i])

        page.locator(f'//div[contains(@id,"{state}-schedule-entry-solar_rad")]/input').fill(solar_rad[i])

        page.locator(f'//div[contains(@id,"{state}-schedule-entry-lux")]/input').fill(lux[i])

        wday_checkbox = page.locator(f'//div[contains(@id,"{state}-schedule-entry-wday")]/span/input')
        for j in range(7):
            if enable_wday_index[i * 7 + j]:
                wday_checkbox.nth(j).check()
            else:
                wday_checkbox.nth(j).uncheck()

        if i != enable_schedule_index:
            enable_checkbox.nth(i).evaluate("node => node.click()")

    page.get_by_test_id("save").click()

    check_log(page, "スケジュールを更新")

    check_schedule(page, enable_schedule_index, schedule_time, solar_rad, lux, enable_wday_index)

    page.reload()

    check_schedule(page, enable_schedule_index, schedule_time, solar_rad, lux, enable_wday_index)


def test_schedule_run(page, host, port):
    page.goto(app_url(host, port), wait_until="domcontentloaded", timeout=30000)

    page.get_by_test_id("clear").click()
    time.sleep(3)  # Wait for log processing
    check_log(page, "ログがクリアされました")

    # NOTE: テスト用APIで時刻を設定（固定時刻で確実にテストできるようにする）
    # 12:00:55に設定して、12:01に閉めるスケジュールが実行されるようにする
    current_time = my_lib.time.now().replace(hour=12, minute=0, second=45)
    set_mock_time(host, port, current_time)
    get_current_server_time(host, port)

    # NOTE: スケジュールに従って閉める評価をしたいので、一旦あけておく
    page.get_by_test_id("open-0").click()
    page.get_by_test_id("open-1").click()

    for state in ["open", "close"]:
        # NOTE: checkbox 自体は hidden にして、CSS で表示しているので、
        # 通常の locator では操作できない
        enable_checkbox = page.locator(f'//input[contains(@id,"{state}-schedule-entry")]')
        enable_checkbox.evaluate("node => node.checked = false")
        enable_checkbox.evaluate("node => node.click()")

        if state == "close":
            # モック時間ベースで1分後の時刻を計算
            schedule_time = (current_time + datetime.timedelta(minutes=SCHEDULE_AFTER_MIN)).strftime("%H:%M")
        else:
            schedule_time = "08:00"

        logging.info("Set schedule %s: %s", state, schedule_time)

        page.locator(f'//div[contains(@id,"{state}-schedule-entry-time")]/input').fill(schedule_time)

        # solar_rad、lux、altitude の値をランダムに設定（確実に変更を検出させるため）
        page.locator(f'//div[contains(@id,"{state}-schedule-entry-solar_rad")]/input').fill(
            str(100 + int(100 * random.random()))  # noqa: S311
        )
        page.locator(f'//div[contains(@id,"{state}-schedule-entry-lux")]/input').fill(
            str(500 + int(500 * random.random()))  # noqa: S311
        )
        page.locator(f'//div[contains(@id,"{state}-schedule-entry-altitude")]/input').fill(
            str(10 + int(20 * random.random()))  # noqa: S311
        )

        # NOTE: 曜日は全てチェック
        wday_checkbox = page.locator(f'//div[contains(@id,"{state}-schedule-entry-wday")]/span/input')
        for j in range(7):
            wday_checkbox.nth(j).check()

    logging.info("Save shcedule")
    page.get_by_test_id("save").click()
    check_log(page, "スケジュールを更新")

    time.sleep(15)

    check_log(page, "スケジューラで閉めました", 10)


def test_schedule_disable(page, host, port):
    page.goto(app_url(host, port), wait_until="domcontentloaded", timeout=30000)

    page.get_by_test_id("clear").click()
    time.sleep(3)  # Wait longer for log processing
    check_log(page, "ログがクリアされました")

    # NOTE: スケジュールに従って閉める評価をしたいので、一旦あけておく
    page.get_by_test_id("open-0").click()
    page.get_by_test_id("open-1").click()
    time.sleep(1)

    # NOTE: テスト用APIで時刻を設定
    current_time = my_lib.time.now().replace(second=30, microsecond=0)
    set_mock_time(host, port, current_time)
    logging.info("Mock time set for disable test")

    for state in ["open", "close"]:
        # NOTE: checkbox 自体は hidden にして、CSS で表示しているので、
        # 通常の locator では操作できない
        enable_checkbox = page.locator(f'//input[contains(@id,"{state}-schedule-entry")]')
        enable_checkbox.evaluate("node => node.checked = false")
        enable_checkbox.evaluate("node => node.click()")

        # NOTE: 1分後にスケジュール設定
        page.locator(f'//div[contains(@id,"{state}-schedule-entry-time")]/input').fill(time_str_after(1))

        # NOTE: 曜日は全てチェック
        wday_checkbox = page.locator(f'//div[contains(@id,"{state}-schedule-entry-wday")]/span/input')
        for j in range(7):
            wday_checkbox.nth(j).check()

        # NOTE: スケジュールを無効に設定
        enable_checkbox.evaluate("node => node.click()")

    page.get_by_test_id("save").click()
    check_log(page, "スケジュールを更新")

    # NOTE: 何も実行されていないことを確認
    advance_mock_time(host, port, 60)
    # API使用時は短時間で確認
    time.sleep(0.5)  # さらに短縮
    check_log(page, "スケジュールを更新")
