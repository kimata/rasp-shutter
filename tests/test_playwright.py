#!/usr/bin/env python3
# ruff: noqa: S101

import datetime
import pathlib
import random
import sys
import time

from flaky import flaky
from playwright.sync_api import expect

sys.path.append(str(pathlib.Path(__file__).parent.parent / "flask" / "lib"))

import my_lib.webapp.config

APP_URL_TMPL = "http://{host}:{port}/rasp-shutter/"

SCHEDULE_AFTER_MIN = 1


def check_log(page, message, timeout_sec=2):
    expect(page.locator('//div[contains(@class,"log")]/div/div[2]').first).to_contain_text(
        message, timeout=timeout_sec * 1000
    )

    # NOTE: ログクリアする場合，ログの内容が変化しているので，ここで再取得する
    log_list = page.locator('//div[contains(@class,"log")]/div/div[2]')
    for i in range(log_list.count()):
        expect(log_list.nth(i)).not_to_contain_text("失敗")
        expect(log_list.nth(i)).not_to_contain_text("エラー")


def time_str_random():
    return f"{int(24 * random.random()):02d}:{int(60 * random.random()):02d}"  # noqa: S311


def time_str_after(min_value):
    return (
        datetime.datetime.now(my_lib.webapp.config.TIMEZONE) + datetime.timedelta(minutes=min_value)
    ).strftime("%H:%M")


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


def init(page):
    page.on("console", lambda msg: msg.text)
    page.set_viewport_size({"width": 2400, "height": 1600})


######################################################################
def test_time():
    import logging

    import schedule

    logging.debug("datetime.now()                 = %s", datetime.datetime.now())  # noqa: DTZ005
    logging.debug("datetime.now(JST)              = %s", datetime.datetime.now(my_lib.webapp.config.TIMEZONE))
    logging.debug(
        "datetime.now().replace(...)    = %s",
        datetime.datetime.now().replace(hour=0, minute=0, second=0),  # noqa: DTZ005
    )
    logging.debug(
        "datetime.now(JST).replace(...) = %s",
        datetime.datetime.now(my_lib.webapp.config.TIMEZONE).replace(hour=0, minute=0, second=0),
    )

    schedule.clear()
    job_time_str = time_str_after(SCHEDULE_AFTER_MIN)
    logging.debug("set schedule at %s", job_time_str)
    job = schedule.every().day.at(job_time_str, my_lib.webapp.config.TIMEZONE_PYTZ).do(lambda: True)

    idle_sec = schedule.idle_seconds()
    logging.debug("Time to next jobs is %.1f sec", idle_sec)
    logging.debug("Next run is %s", job.next_run)

    assert idle_sec < 60


@flaky(max_runs=3, min_passes=1)
def test_manual(page, host, port):
    init(page)
    page.goto(app_url(host, port))

    page.get_by_test_id("clear").click()
    time.sleep(1)
    check_log(page, "ログがクリアされました")

    # NOTE: 連続してテスト実行する場合に open がはじかれないようにまず閉める
    page.get_by_test_id("close-0").click()
    time.sleep(1)

    page.get_by_test_id("open-0").click()
    check_log(page, "手動で開けました")

    page.get_by_test_id("open-1").click()
    check_log(page, "手動で開けました")

    page.get_by_test_id("close-0").click()
    check_log(page, "手動で閉めました")

    page.get_by_test_id("close-0").click()
    check_log(page, "閉めるのを見合わせました")

    page.get_by_test_id("close-1").click()
    check_log(page, "手動で閉めました")

    page.get_by_test_id("open-0").click()
    check_log(page, "手動で開けました")

    page.get_by_test_id("open-0").click()
    check_log(page, "開けるのを見合わせました")

    page.get_by_test_id("open-1").click()
    check_log(page, "手動で開けました")

    time.sleep(60)

    page.get_by_test_id("open-1").click()
    check_log(page, "手動で開けました")


@flaky(max_runs=3, min_passes=1)
def test_schedule(page, host, port):
    init(page)
    page.goto(app_url(host, port))

    page.get_by_test_id("clear").click()
    time.sleep(1)
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


@flaky(max_runs=3, min_passes=1)
def test_schedule_run(page, host, port):
    init(page)
    page.goto(app_url(host, port))

    page.get_by_test_id("clear").click()
    time.sleep(1)
    check_log(page, "ログがクリアされました")

    # NOTE: 次の「分」で実行させるにあたって，秒数を調整する
    time.sleep((90 - datetime.datetime.now(my_lib.webapp.config.TIMEZONE).second) % 60)

    # NOTE: スケジュールに従って閉める評価をしたいので，一旦あけておく
    page.get_by_test_id("open-0").click()
    page.get_by_test_id("open-1").click()

    for state in ["open", "close"]:
        # NOTE: checkbox 自体は hidden にして，CSS で表示しているので，
        # 通常の locator では操作できない
        enable_checkbox = page.locator(f'//input[contains(@id,"{state}-schedule-entry")]')
        enable_checkbox.evaluate("node => node.checked = false")
        enable_checkbox.evaluate("node => node.click()")

        schedule_time = time_str_after(SCHEDULE_AFTER_MIN) if state == "close" else time_str_random()
        page.locator(f'//div[contains(@id,"{state}-schedule-entry-time")]/input').fill(schedule_time)

        # NOTE: 曜日は全てチェック
        wday_checkbox = page.locator(f'//div[contains(@id,"{state}-schedule-entry-wday")]/span/input')
        for j in range(7):
            wday_checkbox.nth(j).check()

    page.get_by_test_id("save").click()
    check_log(page, "スケジュールを更新")

    check_log(page, "閉めました", (SCHEDULE_AFTER_MIN * 60) + 10)


@flaky(max_runs=3, min_passes=1)
def test_schedule_disable(page, host, port):
    init(page)
    page.goto(app_url(host, port))

    page.get_by_test_id("clear").click()
    time.sleep(1)
    check_log(page, "ログがクリアされました")

    # NOTE: スケジュールに従って閉める評価をしたいので，一旦あけておく
    page.get_by_test_id("open-0").click()
    page.get_by_test_id("open-1").click()
    time.sleep(1)

    for state in ["open", "close"]:
        # NOTE: checkbox 自体は hidden にして，CSS で表示しているので，
        # 通常の locator では操作できない
        enable_checkbox = page.locator(f'//input[contains(@id,"{state}-schedule-entry")]')
        enable_checkbox.evaluate("node => node.checked = false")
        enable_checkbox.evaluate("node => node.click()")

        # NOET: 1分後にスケジュール設定
        page.locator(f'//div[contains(@id,"{state}-schedule-entry-time")]/input').fill(time_str_after(1))

        # NOTE: 曜日は全てチェック
        wday_checkbox = page.locator(f'//div[contains(@id,"{state}-schedule-entry-wday")]/span/input')
        for j in range(7):
            wday_checkbox.nth(j).check()

        # NOTE: スケジュールを無効に設定
        enable_checkbox.evaluate("node => node.click()")

    page.get_by_test_id("save").click()
    check_log(page, "スケジュールを更新")

    # NOET: 何も実行されていないことを確認
    time.sleep(60)
    check_log(page, "スケジュールを更新")
