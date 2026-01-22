#!/usr/bin/env python3
# ruff: noqa: S101
"""スケジュール実行確認のE2Eテスト"""

import datetime
import logging
import random
import time

import my_lib.time
from playwright.sync_api import Page

from tests.e2e.conftest import (
    advance_mock_time_and_wait,
    clear_log,
    click_and_check_log,
    get_current_server_time,
    get_scheduler_loop_sequence,
    set_mock_time,
    wait_for_log,
    wait_scheduler_loop,
)

SCHEDULE_AFTER_MIN = 1


class TestScheduleExecution:
    """スケジュール実行のテスト"""

    def test_schedule_run(self, page: Page, host: str, port: str) -> None:
        """スケジュールに従ってシャッターが閉まる"""
        clear_log(page, host, port)

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
                schedule_time = (current_time + datetime.timedelta(minutes=SCHEDULE_AFTER_MIN)).strftime(
                    "%H:%M"
                )
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

        logging.info("Save schedule")

        # スケジュール保存前のループシーケンスを取得
        initial_sequence = get_scheduler_loop_sequence(host, port)
        assert initial_sequence is not None, "Failed to get scheduler loop sequence"
        logging.info("Initial scheduler loop sequence: %d", initial_sequence)

        click_and_check_log(page, host, port, "save", "スケジュールを更新")

        # スケジューラがキューを処理するのを待機（ループシーケンスが進むまで）
        logging.info("Waiting for scheduler to process queue...")
        assert wait_scheduler_loop(host, port, initial_sequence, timeout=10.0), "Scheduler did not process queue"

        # NOTE: スケジュール保存後、モック時間を12:01以降に進めてスケジュールを発火させる
        # advance_mock_time_and_wait を使用して、スケジューラが新しい時刻で run_pending() を
        # 実行するまで待機する
        logging.info("Advancing mock time and waiting for scheduler...")
        assert advance_mock_time_and_wait(host, port, 20, wait_loops=2), "Failed to advance time and wait for scheduler"

        assert wait_for_log(page, "スケジューラで閉めました", timeout_sec=30.0)


class TestTimeAPI:
    """時間API関連のテスト"""

    def test_time(self) -> None:
        """時刻とスケジュールのテスト"""
        import schedule

        logging.debug("datetime.now()                        = %s", datetime.datetime.now())
        logging.debug(
            "datetime.now(%10s)              = %s",
            my_lib.time.get_tz(),
            datetime.datetime.now(my_lib.time.get_zoneinfo()),
        )
        logging.debug(
            "datetime.now().replace(...)           = %s",
            datetime.datetime.now().replace(hour=0, minute=0, second=0),
        )
        logging.debug(
            "datetime.now(%10s).replace(...) = %s",
            my_lib.time.get_tz(),
            my_lib.time.now().replace(hour=0, minute=0, second=0),
        )

        schedule.clear()
        job_time_str = (my_lib.time.now() + datetime.timedelta(minutes=SCHEDULE_AFTER_MIN)).strftime("%H:%M")
        logging.debug("set schedule at %s", job_time_str)
        job = schedule.every().day.at(job_time_str, my_lib.time.get_pytz()).do(lambda: True)

        idle_sec = schedule.idle_seconds()
        assert idle_sec is not None
        logging.debug("Time to next jobs is %.1f sec", idle_sec)
        logging.debug("Next run is %s", job.next_run)

        assert idle_sec < 60
