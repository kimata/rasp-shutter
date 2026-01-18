#!/usr/bin/env python3
# ruff: noqa: S101
"""メトリクスのユニットテスト"""

import datetime
import pathlib
import tempfile

import pytest


class TestMetricsCollector:
    """MetricsCollectorクラスのテスト"""

    @pytest.fixture
    def temp_metrics_path(self):
        """一時メトリクスファイルパス"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield pathlib.Path(tmpdir) / "test_metrics.db"

    def test_create_collector(self, temp_metrics_path):
        """コレクターの作成"""
        import rasp_shutter.metrics.collector

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)

        assert collector is not None
        assert collector.db_path == temp_metrics_path

    def test_record_operation(self, temp_metrics_path):
        """操作記録のテスト"""
        import rasp_shutter.metrics.collector

        from tests.fixtures.sensor_factory import SensorDataFactory

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)

        # 操作を記録
        sensor_data = SensorDataFactory.custom(solar_rad=200, lux=2000, altitude=50)
        collector.record_shutter_operation(
            action="open",
            mode="manual",
            sensor_data=sensor_data,
        )

        # 記録を確認
        metrics = collector.get_all_operation_metrics()
        assert len(metrics) == 1
        assert metrics[0]["action"] == "open"
        assert metrics[0]["operation_type"] == "manual"

    def test_record_failure(self, temp_metrics_path):
        """失敗記録のテスト"""
        import rasp_shutter.metrics.collector

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)

        # 失敗を記録
        collector.record_failure()

        # 記録を確認
        metrics = collector.get_all_failure_metrics()
        assert len(metrics) == 1

    def test_get_operation_metrics_by_date(self, temp_metrics_path):
        """日付範囲でのメトリクス取得"""
        import rasp_shutter.metrics.collector

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)

        # 操作を記録
        now = datetime.datetime.now()
        collector.record_shutter_operation(
            action="close",
            mode="schedule",
            timestamp=now,
        )

        # 日付範囲で取得
        start_date = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        metrics = collector.get_operation_metrics(start_date, end_date)

        assert len(metrics) == 1
        assert metrics[0]["action"] == "close"

    def test_get_recent_operation_metrics(self, temp_metrics_path):
        """最近のメトリクス取得"""
        import rasp_shutter.metrics.collector

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)

        # 操作を記録
        collector.record_shutter_operation(
            action="open",
            mode="auto",
        )

        # 最近30日のメトリクスを取得
        metrics = collector.get_recent_operation_metrics(days=30)

        assert len(metrics) == 1


class TestMetricsStatistics:
    """メトリクス統計のテスト"""

    def test_generate_statistics_empty(self):
        """空のメトリクスでの統計生成"""
        import rasp_shutter.metrics.webapi.page

        stats = rasp_shutter.metrics.webapi.page.generate_statistics([], [])

        assert stats is not None
        assert "total_days" in stats
        assert stats["total_days"] == 0
        assert stats["manual_open_total"] == 0
        assert stats["auto_close_total"] == 0

    def test_generate_statistics_with_data(self):
        """データありでの統計生成"""
        import rasp_shutter.metrics.webapi.page

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        operation_metrics = [
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "date": today,
                "action": "open",
                "operation_type": "manual",
                "solar_rad": 200,
                "lux": 2000,
                "altitude": 50,
            },
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "date": today,
                "action": "close",
                "operation_type": "schedule",
                "solar_rad": 50,
                "lux": 500,
                "altitude": 10,
            },
        ]

        stats = rasp_shutter.metrics.webapi.page.generate_statistics(operation_metrics, [])

        assert stats["manual_open_total"] == 1
        assert stats["auto_close_total"] == 1

    def test_calculate_data_period_empty(self):
        """空データでのデータ期間計算"""
        import rasp_shutter.metrics.webapi.page

        period = rasp_shutter.metrics.webapi.page.calculate_data_period([])

        assert "start_date" in period
        assert "end_date" in period
        assert period["total_days"] == 0

    def test_calculate_data_period_with_data(self):
        """データありでのデータ期間計算"""
        import rasp_shutter.metrics.webapi.page

        now = datetime.datetime.now()
        yesterday = now - datetime.timedelta(days=1)

        operation_metrics = [
            {"timestamp": yesterday.isoformat(), "date": yesterday.strftime("%Y-%m-%d")},
            {"timestamp": now.isoformat(), "date": now.strftime("%Y-%m-%d")},
        ]

        period = rasp_shutter.metrics.webapi.page.calculate_data_period(operation_metrics)

        assert period["total_days"] >= 1


class TestResetCollector:
    """コレクターリセットのテスト"""

    def test_reset_collector(self):
        """コレクターのリセット"""
        import rasp_shutter.metrics.collector

        # リセット前後でエラーが発生しないことを確認
        rasp_shutter.metrics.collector.reset_collector()

        # 再度リセットしてもエラーにならない
        rasp_shutter.metrics.collector.reset_collector()
