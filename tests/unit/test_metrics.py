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


class TestCollectSensorDataByType:
    """_collect_sensor_data_by_type関数のテスト"""

    def test_collect_auto_type_only(self):
        """autoタイプのみのデータ収集"""
        import rasp_shutter.metrics.webapi.page

        operation_metrics = [
            {"operation_type": "auto", "action": "open", "lux": 100, "solar_rad": 50, "altitude": 10},
            {"operation_type": "auto", "action": "close", "lux": 200, "solar_rad": 60, "altitude": 20},
        ]

        result = rasp_shutter.metrics.webapi.page._collect_sensor_data_by_type(operation_metrics, "auto")

        assert result["open_lux"] == [100]
        assert result["close_lux"] == [200]
        assert result["open_solar_rad"] == [50]
        assert result["close_solar_rad"] == [60]
        assert result["open_altitude"] == [10]
        assert result["close_altitude"] == [20]

    def test_collect_schedule_type_only(self):
        """scheduleタイプのみのデータ収集"""
        import rasp_shutter.metrics.webapi.page

        operation_metrics = [
            {"operation_type": "schedule", "action": "open", "lux": 300, "solar_rad": 70, "altitude": 30},
        ]

        result = rasp_shutter.metrics.webapi.page._collect_sensor_data_by_type(operation_metrics, "schedule")

        assert result["open_lux"] == [300]
        assert result["close_lux"] == []

    def test_collect_ignores_other_types(self):
        """指定タイプ以外は無視される"""
        import rasp_shutter.metrics.webapi.page

        operation_metrics = [
            {"operation_type": "auto", "action": "open", "lux": 100},
            {"operation_type": "manual", "action": "open", "lux": 200},
        ]

        result = rasp_shutter.metrics.webapi.page._collect_sensor_data_by_type(operation_metrics, "auto")

        assert result["open_lux"] == [100]
        assert len(result["open_lux"]) == 1

    def test_collect_with_none_values(self):
        """None値は除外される"""
        import rasp_shutter.metrics.webapi.page

        operation_metrics = [
            {"operation_type": "auto", "action": "open", "lux": None, "solar_rad": 50},
        ]

        result = rasp_shutter.metrics.webapi.page._collect_sensor_data_by_type(operation_metrics, "auto")

        assert result["open_lux"] == []
        assert result["open_solar_rad"] == [50]


class TestAutoScheduleIntegration:
    """auto/scheduleタイプの統合テスト（修正されたバグの回帰テスト）"""

    def test_auto_only_data_not_overwritten(self):
        """autoタイプのみのデータがschedule統合で上書きされないこと"""
        import rasp_shutter.metrics.webapi.page

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        operation_metrics = [
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "date": today,
                "operation_type": "auto",
                "action": "open",
                "lux": 1000,
                "solar_rad": 100,
                "altitude": 30,
            },
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "date": today,
                "operation_type": "auto",
                "action": "close",
                "lux": 500,
                "solar_rad": 50,
                "altitude": 15,
            },
        ]

        stats = rasp_shutter.metrics.webapi.page.generate_statistics(operation_metrics, [])

        # autoのデータがschedule統合後も保持されていること
        assert stats["auto_sensor_data"]["open_lux"] == [1000]
        assert stats["auto_sensor_data"]["close_lux"] == [500]
        assert stats["auto_sensor_data"]["open_solar_rad"] == [100]
        assert stats["auto_sensor_data"]["close_solar_rad"] == [50]
        assert stats["auto_sensor_data"]["open_altitude"] == [30]
        assert stats["auto_sensor_data"]["close_altitude"] == [15]

    def test_auto_and_schedule_merged(self):
        """autoとscheduleのデータが正しく統合されること"""
        import rasp_shutter.metrics.webapi.page

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        operation_metrics = [
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "date": today,
                "operation_type": "auto",
                "action": "open",
                "lux": 1000,
            },
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "date": today,
                "operation_type": "schedule",
                "action": "open",
                "lux": 2000,
            },
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "date": today,
                "operation_type": "auto",
                "action": "close",
                "lux": 500,
            },
        ]

        stats = rasp_shutter.metrics.webapi.page.generate_statistics(operation_metrics, [])

        # autoとscheduleのopen_luxが統合されている
        assert 1000 in stats["auto_sensor_data"]["open_lux"]
        assert 2000 in stats["auto_sensor_data"]["open_lux"]
        assert len(stats["auto_sensor_data"]["open_lux"]) == 2

        # close_luxはautoのみ
        assert stats["auto_sensor_data"]["close_lux"] == [500]

    def test_schedule_only_no_auto(self):
        """scheduleタイプのみでautoがない場合"""
        import rasp_shutter.metrics.webapi.page

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        operation_metrics = [
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "date": today,
                "operation_type": "schedule",
                "action": "close",
                "lux": 300,
            },
        ]

        stats = rasp_shutter.metrics.webapi.page.generate_statistics(operation_metrics, [])

        assert stats["auto_sensor_data"]["close_lux"] == [300]
        assert stats["auto_sensor_data"]["open_lux"] == []


class TestResetCollector:
    """コレクターリセットのテスト"""

    def test_reset_collector(self):
        """コレクターのリセット"""
        import rasp_shutter.metrics.collector

        # リセット前後でエラーが発生しないことを確認
        rasp_shutter.metrics.collector.reset_collector()

        # 再度リセットしてもエラーにならない
        rasp_shutter.metrics.collector.reset_collector()
