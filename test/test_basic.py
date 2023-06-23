#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from playwright.sync_api import expect
import random
import datetime
import time
from flaky import flaky

APP_URL_TMPL = "http://{host}:{port}/rasp-shutter/"


def check_log(page, message, timeout_sec=1):
    expect(
        page.locator('//div[contains(@class,"log")]/div/div[2]').first
    ).to_contain_text(message, timeout=timeout_sec * 1000)

    # NOTE: ログクリアする場合，ログの内容が変化しているので，ここで再取得する
    log_list = page.locator('//div[contains(@class,"log")]/div/div[2]')
    for i in range(log_list.count()):
        expect(log_list.nth(i)).not_to_contain_text("失敗")
        expect(log_list.nth(i)).not_to_contain_text("エラー")


def time_str_random():
    return "{hour:02d}:{min:02d}".format(
        hour=int(24 * random.random()), min=int(60 * random.random())
    )


def time_str_after(min):
    return (datetime.datetime.now() + datetime.timedelta(minutes=min)).strftime("%H:%M")


def number_random(min, max):
    return str(int(min + (max - min) * random.random()))


def bool_random():
    return random.random() >= 0.5


def check_schedule(
    page, enable_schedule_index, schedule_time, solar_rad, lux, enable_wday_index
):
    enable_checkbox = page.locator('//input[contains(@id,"-schedule-entry")]')

    for (i, state) in enumerate(["open", "close"]):
        if i == enable_schedule_index:
            expect(enable_checkbox.nth(i)).to_be_checked()
        else:
            expect(enable_checkbox.nth(i)).not_to_be_checked()

        expect(
            page.locator(
                '//div[contains(@id,"{state}-schedule-entry-time")]/input'.format(
                    state=state
                )
            )
        ).to_have_value(schedule_time[i])

        expect(
            page.locator(
                '//div[contains(@id,"{state}-schedule-entry-solar_rad")]/input'.format(
                    state=state
                )
            )
        ).to_have_value(solar_rad[i])

        expect(
            page.locator(
                '//div[contains(@id,"{state}-schedule-entry-lux")]/input'.format(
                    state=state
                )
            )
        ).to_have_value(lux[i])

        wday_checkbox = page.locator(
            '//div[contains(@id,"{state}-schedule-entry-wday")]/span/input'.format(
                state=state
            )
        )
        for j in range(7):
            if enable_wday_index[i * 7 + j]:
                expect(wday_checkbox.nth(j)).to_be_checked()
            else:
                expect(wday_checkbox.nth(j)).not_to_be_checked()


def app_url(server, port):
    return APP_URL_TMPL.format(host=server, port=port)


######################################################################
@flaky(max_runs=5)
def test_manual(page, server, port):
    page.set_viewport_size({"width": 800, "height": 1600})
    page.goto(app_url(server, port))

    page.get_by_test_id("clear").click()
    time.sleep(1)
    check_log(page, "ログがクリアされました")

    # NOTE: 連続してテスト実行する場合に open がはじかれないようにまず閉める
    page.get_by_test_id("close").click()

    page.get_by_test_id("open").click()
    check_log(page, "手動で開けました")

    page.get_by_test_id("close").click()
    check_log(page, "手動で閉めました")

    page.get_by_test_id("close").click()
    check_log(page, "閉めるのを見合わせました")

    page.get_by_test_id("open").click()
    check_log(page, "手動で開けました")

    page.get_by_test_id("open").click()
    check_log(page, "開けるのを見合わせました")

    time.sleep(60)

    page.get_by_test_id("open").click()
    check_log(page, "手動で開けました")


@flaky(max_runs=5)
def test_schedule(page, server, port):
    page.set_viewport_size({"width": 800, "height": 1600})
    page.goto(app_url(server, port))

    page.get_by_test_id("clear").click()
    time.sleep(1)
    check_log(page, "ログがクリアされました")

    # NOTE: ランダムなスケジュール設定を準備
    schedule_time = [time_str_random(), time_str_random()]
    solar_rad = [number_random(100, 200), number_random(100, 200)]
    lux = [number_random(500, 2000), number_random(500, 2000)]
    enable_wday_index = [bool_random() for _ in range(14)]
    enable_schedule_index = int(2 * random.random())
    enable_checkbox = page.locator('//input[contains(@id,"-schedule-entry")]')
    for (i, state) in enumerate(["open", "close"]):
        # NTE: 最初に強制的に有効にしておく
        enable_checkbox.nth(i).evaluate("node => node.checked = false")
        enable_checkbox.nth(i).evaluate("node => node.click()")

        page.locator(
            '//div[contains(@id,"{state}-schedule-entry-time")]/input'.format(
                state=state
            )
        ).fill(schedule_time[i])

        page.locator(
            '//div[contains(@id,"{state}-schedule-entry-solar_rad")]/input'.format(
                state=state
            )
        ).fill(solar_rad[i])

        page.locator(
            '//div[contains(@id,"{state}-schedule-entry-lux")]/input'.format(
                state=state
            )
        ).fill(lux[i])

        wday_checkbox = page.locator(
            '//div[contains(@id,"{state}-schedule-entry-wday")]/span/input'.format(
                state=state
            )
        )
        for j in range(7):
            if enable_wday_index[i * 7 + j]:
                wday_checkbox.nth(j).check()
            else:
                wday_checkbox.nth(j).uncheck()

        if i != enable_schedule_index:
            enable_checkbox.nth(i).evaluate("node => node.click()")

    page.get_by_test_id("save").click()

    check_log(page, "スケジュールを更新")

    check_schedule(
        page, enable_schedule_index, schedule_time, solar_rad, lux, enable_wday_index
    )

    page.reload()

    check_schedule(
        page, enable_schedule_index, schedule_time, solar_rad, lux, enable_wday_index
    )


@flaky(max_runs=5)
def test_schedule_run(page, server, port):
    SCHEDULE_AFTER_MIN = 2

    page.set_viewport_size({"width": 800, "height": 1600})
    page.goto(app_url(server, port))

    page.get_by_test_id("clear").click()
    time.sleep(1)
    check_log(page, "ログがクリアされました")

    # NOTE: スケジュールに従って閉める評価をしたいので，一旦あけておく
    page.get_by_test_id("open").click()

    for (i, state) in enumerate(["open", "close"]):
        # NOTE: checkbox 自体は hidden にして，CSS で表示しているので，
        # 通常の locator では操作できない
        enable_checkbox = page.locator(
            '//input[contains(@id,"{state}-schedule-entry")]'.format(state=state)
        )
        enable_checkbox.evaluate("node => node.checked = false")
        enable_checkbox.evaluate("node => node.click()")

        if state == "close":
            schedule_time = time_str_after(SCHEDULE_AFTER_MIN)
        else:
            schedule_time = time_str_random()
        page.locator(
            '//div[contains(@id,"{state}-schedule-entry-time")]/input'.format(
                state=state
            )
        ).fill(schedule_time)

        # NOTE: 曜日は全てチェック
        wday_checkbox = page.locator(
            '//div[contains(@id,"{state}-schedule-entry-wday")]/span/input'.format(
                state=state
            )
        )
        for j in range(7):
            wday_checkbox.nth(j).check()

    page.get_by_test_id("save").click()
    check_log(page, "スケジュールを更新")

    check_log(page, "閉めました", SCHEDULE_AFTER_MIN * 60 + 10)


@flaky(max_runs=5)
def test_schedule_disable(page, server, port):
    page.set_viewport_size({"width": 800, "height": 1600})
    page.goto(app_url(server, port))

    page.get_by_test_id("clear").click()
    time.sleep(1)
    check_log(page, "ログがクリアされました")

    # NOTE: スケジュールに従って閉める評価をしたいので，一旦あけておく
    page.get_by_test_id("open").click()

    for (i, state) in enumerate(["open", "close"]):
        # NOTE: checkbox 自体は hidden にして，CSS で表示しているので，
        # 通常の locator では操作できない
        enable_checkbox = page.locator(
            '//input[contains(@id,"{state}-schedule-entry")]'.format(state=state)
        )
        enable_checkbox.evaluate("node => node.checked = false")
        enable_checkbox.evaluate("node => node.click()")

        # NOET: 1分後にスケジュール設定
        page.locator(
            '//div[contains(@id,"{state}-schedule-entry-time")]/input'.format(
                state=state
            )
        ).fill(time_str_after(1))

        # NOTE: 曜日は全てチェック
        wday_checkbox = page.locator(
            '//div[contains(@id,"{state}-schedule-entry-wday")]/span/input'.format(
                state=state
            )
        )
        for j in range(7):
            wday_checkbox.nth(j).check()

        # NOTE: スケジュールを無効に設定
        enable_checkbox.evaluate("node => node.click()")

    page.get_by_test_id("save").click()
    check_log(page, "スケジュールを更新")

    # NOET: 何も実行されていないことを確認
    time.sleep(60)
    check_log(page, "スケジュールを更新")
