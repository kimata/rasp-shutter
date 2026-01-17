#!/usr/bin/env python3
"""スケジュール設定UIのE2Eテスト"""

import random
import time

import my_lib.time
from playwright.sync_api import Page

from tests.e2e.conftest import (
    advance_mock_time,
    bool_random,
    check_schedule,
    clear_log,
    click_and_check_log,
    number_random,
    set_mock_time,
    time_str_after,
    time_str_random,
)


class TestScheduleUI:
    """スケジュール設定UIのテスト"""

    def test_schedule_settings(self, page: Page, host: str, port: str) -> None:
        """スケジュールを設定できる"""
        clear_log(page, host, port)

        # NOTE: ランダムなスケジュール設定を準備
        schedule_time = [time_str_random(), time_str_random()]
        solar_rad = [number_random(100, 200), number_random(100, 200)]
        lux = [number_random(500, 2000), number_random(500, 2000)]
        enable_wday_index = [bool_random() for _ in range(14)]
        enable_schedule_index = int(2 * random.random())  # noqa: S311
        enable_checkbox = page.locator('//input[contains(@id,"-schedule-entry")]')

        for i, state in enumerate(["open", "close"]):
            # NOTE: 最初に強制的に有効にしておく
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

        click_and_check_log(page, host, port, "save", "スケジュールを更新")

        check_schedule(page, enable_schedule_index, schedule_time, solar_rad, lux, enable_wday_index)

        page.reload()

        check_schedule(page, enable_schedule_index, schedule_time, solar_rad, lux, enable_wday_index)

    def test_schedule_disable(self, page: Page, host: str, port: str) -> None:
        """無効なスケジュールでは動作しない"""
        clear_log(page, host, port)

        # NOTE: スケジュールに従って閉める評価をしたいので、一旦あけておく
        page.get_by_test_id("open-0").click()
        page.get_by_test_id("open-1").click()
        time.sleep(5)

        # NOTE: テスト用APIで時刻を設定
        current_time = my_lib.time.now().replace(second=30, microsecond=0)
        set_mock_time(host, port, current_time)

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

        click_and_check_log(page, host, port, "save", "スケジュールを更新")

        # NOTE: 何も実行されていないことを確認
        advance_mock_time(host, port, 60)
        from tests.e2e.conftest import check_log

        check_log(page, "スケジュールを更新")
