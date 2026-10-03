#!/usr/bin/env python3
# ruff: noqa: S101
"""センサー値の張り付き監視のユニットテスト"""

import datetime

import my_lib.time
import pytest

import rasp_shutter.control.config
import rasp_shutter.control.sensor_watch
from tests.fixtures.sensor_factory import SensorDataFactory

DURATION = datetime.timedelta(seconds=rasp_shutter.control.config.SENSOR_STUCK_DURATION_SEC)
SAMPLE_INTERVAL = datetime.timedelta(minutes=1)

# 太陽高度（判定対象 / 判定対象外）
ALTITUDE_DAY = rasp_shutter.control.config.SENSOR_STUCK_ALTITUDE_MIN_DEG + 20
ALTITUDE_NIGHT = rasp_shutter.control.config.SENSOR_STUCK_ALTITUDE_MIN_DEG - 1


@pytest.fixture
def watcher():
    return rasp_shutter.control.sensor_watch.SensorStuckWatcher()


@pytest.fixture
def log_error(mocker):
    return mocker.patch("my_lib.webapp.log.error")


@pytest.fixture
def log_info(mocker):
    return mocker.patch("my_lib.webapp.log.info")


def _morning(day: int = 1) -> datetime.datetime:
    return datetime.datetime(2026, 10, day, 9, 0, tzinfo=my_lib.time.get_zoneinfo())


def _feed(watcher, start: datetime.datetime, duration: datetime.timedelta, **sensor_kwargs) -> None:
    """start から duration の間、1 分間隔で同じセンサー値を与える（終端を含む）"""
    sense_data = SensorDataFactory.custom(**sensor_kwargs)
    now = start
    while now <= start + duration:
        watcher.check(sense_data, now)
        now += SAMPLE_INTERVAL


class TestSensorStuckWatcher:
    """SensorStuckWatcher のテスト"""

    def test_normal_value_is_not_notified(self, watcher, log_error, log_info):
        """正常な値では通知しない"""
        _feed(watcher, _morning(), DURATION * 2, lux=2000, solar_rad=200, altitude=ALTITUDE_DAY)

        log_error.assert_not_called()
        log_info.assert_not_called()

    def test_zero_shorter_than_duration_is_not_notified(self, watcher, log_error):
        """0 の継続が判定時間に満たない場合は通知しない"""
        _feed(watcher, _morning(), DURATION - SAMPLE_INTERVAL, lux=0, solar_rad=200, altitude=ALTITUDE_DAY)

        log_error.assert_not_called()

    def test_lux_stuck_is_notified(self, watcher, log_error):
        """太陽が高いのに照度が 0 のままなら通知する"""
        _feed(watcher, _morning(), DURATION, lux=0, solar_rad=200, altitude=ALTITUDE_DAY)

        log_error.assert_called_once()
        message = log_error.call_args.args[0]
        assert "照度センサの値" in message
        assert "日射センサ" not in message
        assert "30 分以上 0 のまま" in message
        assert "照度: 0.0 LUX" in message

    def test_solar_rad_stuck_is_notified(self, watcher, log_error):
        """太陽が高いのに日射が 0 のままなら通知する"""
        _feed(watcher, _morning(), DURATION, lux=2000, solar_rad=0, altitude=ALTITUDE_DAY)

        log_error.assert_called_once()
        message = log_error.call_args.args[0]
        assert "日射センサの値" in message
        assert "照度センサ" not in message

    def test_both_stuck_is_notified_at_once(self, watcher, log_error):
        """両方のセンサーが同時に張り付いた場合は 1 回の通知にまとめる"""
        _feed(watcher, _morning(), DURATION, lux=0, solar_rad=0, altitude=ALTITUDE_DAY)

        log_error.assert_called_once()
        assert "照度センサと日射センサの値" in log_error.call_args.args[0]

    def test_night_is_not_notified(self, watcher, log_error):
        """太陽高度が低い時間帯は 0 が続いても通知しない"""
        _feed(watcher, _morning(), DURATION * 20, lux=0, solar_rad=0, altitude=ALTITUDE_NIGHT)

        log_error.assert_not_called()

    def test_invalid_altitude_is_not_notified(self, watcher, log_error):
        """太陽高度が不明な場合は通知しない"""
        _feed(watcher, _morning(), DURATION * 2, lux=0, solar_rad=0, altitude_valid=False)

        log_error.assert_not_called()

    def test_invalid_sensor_is_not_notified(self, watcher, log_error):
        """センサー値が取得できない場合は張り付きとして扱わない"""
        _feed(watcher, _morning(), DURATION * 2, lux_valid=False, solar_rad=200, altitude=ALTITUDE_DAY)

        log_error.assert_not_called()

    def test_duration_is_reset_by_non_zero_value(self, watcher, log_error):
        """途中で 0 以外の値に戻ると、継続時間の計測をやり直す"""
        start = _morning()
        half = DURATION / 2

        _feed(watcher, start, half, lux=0, solar_rad=200, altitude=ALTITUDE_DAY)
        watcher.check(SensorDataFactory.custom(lux=100, solar_rad=200, altitude=ALTITUDE_DAY), start + half)
        _feed(watcher, start + half + SAMPLE_INTERVAL, half, lux=0, solar_rad=200, altitude=ALTITUDE_DAY)

        log_error.assert_not_called()

    def test_duration_is_reset_at_night(self, watcher, log_error):
        """日中の 0 と翌日の 0 を、夜間をまたいで合算しない"""
        half = DURATION / 2

        _feed(watcher, _morning(1), half, lux=0, solar_rad=200, altitude=ALTITUDE_DAY)
        night_data = SensorDataFactory.custom(lux=0, solar_rad=0, altitude=ALTITUDE_NIGHT)
        watcher.check(night_data, _morning(1) + DURATION)
        _feed(watcher, _morning(2), half, lux=0, solar_rad=200, altitude=ALTITUDE_DAY)

        log_error.assert_not_called()

    def test_notified_once_a_day(self, watcher, log_error):
        """異常が続いている間、同じ日には再通知しない"""
        _feed(watcher, _morning(), DURATION * 6, lux=0, solar_rad=200, altitude=ALTITUDE_DAY)

        log_error.assert_called_once()

    def test_notified_again_next_day(self, watcher, log_error):
        """異常が翌日も続いている場合は、1 日 1 回のペースで再通知する"""
        for day in [1, 2, 3]:
            _feed(watcher, _morning(day), DURATION * 6, lux=0, solar_rad=200, altitude=ALTITUDE_DAY)
            _feed(
                watcher,
                _morning(day) + datetime.timedelta(hours=10),
                DURATION,
                lux=0,
                solar_rad=0,
                altitude=ALTITUDE_NIGHT,
            )

            assert log_error.call_count == day

    def test_recovery_is_logged(self, watcher, log_error, log_info):
        """通知後に値が戻った場合は復旧を記録し、再度張り付いたら同日でも通知する"""
        start = _morning()

        _feed(watcher, start, DURATION, lux=0, solar_rad=200, altitude=ALTITUDE_DAY)
        log_info.assert_not_called()

        recovered_at = start + DURATION + SAMPLE_INTERVAL
        _feed(watcher, recovered_at, DURATION, lux=2000, solar_rad=200, altitude=ALTITUDE_DAY)
        log_info.assert_called_once()
        assert "照度センサの値が 0 以外に戻りました" in log_info.call_args.args[0]

        _feed(watcher, recovered_at + DURATION * 2, DURATION, lux=0, solar_rad=200, altitude=ALTITUDE_DAY)
        assert log_error.call_count == 2

    def test_recovery_at_night_is_logged(self, watcher, log_error, log_info):
        """夜間でも 0 以外の値が得られれば復旧として扱う"""
        start = _morning()

        _feed(watcher, start, DURATION, lux=0, solar_rad=200, altitude=ALTITUDE_DAY)
        watcher.check(
            SensorDataFactory.custom(lux=5, solar_rad=0, altitude=ALTITUDE_NIGHT),
            start + datetime.timedelta(hours=9),
        )

        log_error.assert_called_once()
        log_info.assert_called_once()
