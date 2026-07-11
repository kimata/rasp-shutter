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

    def test_record_postpone(self, temp_metrics_path):
        """見合わせイベント記録のテスト"""
        import rasp_shutter.metrics.collector
        from tests.fixtures.sensor_factory import SensorDataFactory

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)
        sensor_data = SensorDataFactory.custom(solar_rad=100, lux=500, altitude=10)

        recorded = collector.record_postpone(
            intended_action="open",
            trigger="schedule",
            reason="too_dark",
            sensor_data=sensor_data,
            threshold={"lux": 1000, "solar_rad": 200, "altitude": 5},
        )
        assert recorded is True

        events = collector.get_recent_postpone_events(1)
        assert len(events) == 1
        assert events[0]["intended_action"] == "open"
        assert events[0]["reason"] == "too_dark"
        assert events[0]["lux"] == 500.0
        assert events[0]["threshold_lux"] == 1000.0
        assert events[0]["resolved_at"] is None

    def test_postpone_cooldown_suppresses_duplicates(self, temp_metrics_path):
        """同条件のpostponeがクールダウン内なら抑制される"""
        import rasp_shutter.metrics.collector

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)

        first = collector.record_postpone(
            intended_action="open",
            trigger="schedule",
            reason="too_dark",
        )
        second = collector.record_postpone(
            intended_action="open",
            trigger="schedule",
            reason="too_dark",
        )
        assert first is True
        assert second is False

        # クールダウンを短く設定すれば記録される
        third = collector.record_postpone(
            intended_action="open",
            trigger="schedule",
            reason="too_dark",
            cooldown_sec=0.0,
        )
        assert third is True

    def test_postpone_resolved_by_operation(self, temp_metrics_path):
        """同日同方向のoperation記録でpostponeがresolveされる"""
        import rasp_shutter.metrics.collector

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)
        collector.record_postpone(intended_action="open", trigger="schedule", reason="too_dark")
        events_before = collector.get_recent_postpone_events(1)
        assert events_before[0]["resolved_at"] is None

        collector.record_shutter_operation(action="open", mode="auto")

        events_after = collector.get_recent_postpone_events(1)
        assert events_after[0]["resolved_at"] is not None
        assert events_after[0]["resolved_operation_id"] is not None

    def test_postpone_not_resolved_for_other_action(self, temp_metrics_path):
        """違う方向のoperationではresolveされない"""
        import rasp_shutter.metrics.collector

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)
        collector.record_postpone(intended_action="open", trigger="schedule", reason="too_dark")
        collector.record_shutter_operation(action="close", mode="auto")

        events = collector.get_recent_postpone_events(1)
        assert events[0]["resolved_at"] is None

    def test_record_sensor_sample(self, temp_metrics_path):
        """センサーサンプル記録のテスト"""
        import rasp_shutter.metrics.collector
        from tests.fixtures.sensor_factory import SensorDataFactory

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)
        sensor_data = SensorDataFactory.custom(solar_rad=150, lux=800, altitude=15)

        collector.record_sensor_sample(sensor_data, context="auto_open_window")

        samples = collector.get_recent_sensor_samples(1)
        assert len(samples) == 1
        assert samples[0]["lux"] == 800.0
        assert samples[0]["context"] == "auto_open_window"


class TestMetricsStatistics:
    """メトリクス統計のテスト"""

    def test_generate_statistics_empty(self):
        """空のメトリクスでの統計生成"""
        import rasp_shutter.metrics.analyzer

        stats = rasp_shutter.metrics.analyzer.generate_statistics([], [])

        assert stats is not None
        assert "total_days" in stats
        assert stats["total_days"] == 0
        assert stats["manual_open_total"] == 0
        assert stats["auto_close_total"] == 0

    def test_generate_statistics_with_data(self):
        """データありでの統計生成"""
        import rasp_shutter.metrics.analyzer

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

        stats = rasp_shutter.metrics.analyzer.generate_statistics(operation_metrics, [])

        assert stats["manual_open_total"] == 1
        assert stats["auto_close_total"] == 1

    def test_calculate_data_period_empty(self):
        """空データでのデータ期間計算"""
        import rasp_shutter.metrics.analyzer

        period = rasp_shutter.metrics.analyzer.calculate_data_period([])

        assert "start_date" in period
        assert "end_date" in period
        assert period["total_days"] == 0

    def test_calculate_data_period_with_data(self):
        """データありでのデータ期間計算"""
        import rasp_shutter.metrics.analyzer

        now = datetime.datetime.now()
        yesterday = now - datetime.timedelta(days=1)

        operation_metrics = [
            {"timestamp": yesterday.isoformat(), "date": yesterday.strftime("%Y-%m-%d")},
            {"timestamp": now.isoformat(), "date": now.strftime("%Y-%m-%d")},
        ]

        period = rasp_shutter.metrics.analyzer.calculate_data_period(operation_metrics)

        assert period["total_days"] >= 1


class TestCollectSensorDataByType:
    """_collect_sensor_data_by_type関数のテスト"""

    def test_collect_auto_type_only(self):
        """autoタイプのみのデータ収集"""
        import rasp_shutter.metrics.analyzer

        operation_metrics = [
            {"operation_type": "auto", "action": "open", "lux": 100, "solar_rad": 50, "altitude": 10},
            {"operation_type": "auto", "action": "close", "lux": 200, "solar_rad": 60, "altitude": 20},
        ]

        result = rasp_shutter.metrics.analyzer._collect_sensor_data_by_type(operation_metrics, "auto")

        assert result["open_lux"] == [100]
        assert result["close_lux"] == [200]
        assert result["open_solar_rad"] == [50]
        assert result["close_solar_rad"] == [60]
        assert result["open_altitude"] == [10]
        assert result["close_altitude"] == [20]

    def test_collect_schedule_type_only(self):
        """scheduleタイプのみのデータ収集"""
        import rasp_shutter.metrics.analyzer

        operation_metrics = [
            {"operation_type": "schedule", "action": "open", "lux": 300, "solar_rad": 70, "altitude": 30},
        ]

        result = rasp_shutter.metrics.analyzer._collect_sensor_data_by_type(operation_metrics, "schedule")

        assert result["open_lux"] == [300]
        assert result["close_lux"] == []

    def test_collect_ignores_other_types(self):
        """指定タイプ以外は無視される"""
        import rasp_shutter.metrics.analyzer

        operation_metrics = [
            {"operation_type": "auto", "action": "open", "lux": 100},
            {"operation_type": "manual", "action": "open", "lux": 200},
        ]

        result = rasp_shutter.metrics.analyzer._collect_sensor_data_by_type(operation_metrics, "auto")

        assert result["open_lux"] == [100]
        assert len(result["open_lux"]) == 1

    def test_collect_with_none_values(self):
        """None値は除外される"""
        import rasp_shutter.metrics.analyzer

        operation_metrics = [
            {"operation_type": "auto", "action": "open", "lux": None, "solar_rad": 50},
        ]

        result = rasp_shutter.metrics.analyzer._collect_sensor_data_by_type(operation_metrics, "auto")

        assert result["open_lux"] == []
        assert result["open_solar_rad"] == [50]


class TestAutoScheduleIntegration:
    """auto/scheduleタイプの統合テスト（修正されたバグの回帰テスト）"""

    def test_auto_only_data_not_overwritten(self):
        """autoタイプのみのデータがschedule統合で上書きされないこと"""
        import rasp_shutter.metrics.analyzer

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

        stats = rasp_shutter.metrics.analyzer.generate_statistics(operation_metrics, [])

        # autoのデータがschedule統合後も保持されていること
        assert stats["auto_sensor_data"]["open_lux"] == [1000]
        assert stats["auto_sensor_data"]["close_lux"] == [500]
        assert stats["auto_sensor_data"]["open_solar_rad"] == [100]
        assert stats["auto_sensor_data"]["close_solar_rad"] == [50]
        assert stats["auto_sensor_data"]["open_altitude"] == [30]
        assert stats["auto_sensor_data"]["close_altitude"] == [15]

    def test_auto_and_schedule_merged(self):
        """autoとscheduleのデータが正しく統合されること"""
        import rasp_shutter.metrics.analyzer

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

        stats = rasp_shutter.metrics.analyzer.generate_statistics(operation_metrics, [])

        # autoとscheduleのopen_luxが統合されている
        assert 1000 in stats["auto_sensor_data"]["open_lux"]
        assert 2000 in stats["auto_sensor_data"]["open_lux"]
        assert len(stats["auto_sensor_data"]["open_lux"]) == 2

        # close_luxはautoのみ
        assert stats["auto_sensor_data"]["close_lux"] == [500]

    def test_schedule_only_no_auto(self):
        """scheduleタイプのみでautoがない場合"""
        import rasp_shutter.metrics.analyzer

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

        stats = rasp_shutter.metrics.analyzer.generate_statistics(operation_metrics, [])

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


class TestSchemaMigration:
    """既存 DB のスキーママイグレーションのテスト"""

    @pytest.fixture
    def old_schema_db_path(self):
        """shutter 列を持たない旧スキーマの DB を作成"""
        import sqlite3

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = pathlib.Path(tmpdir) / "old_metrics.db"
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE operation_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    date TEXT NOT NULL,
                    action TEXT NOT NULL CHECK (action IN ('open', 'close')),
                    operation_type TEXT NOT NULL CHECK (operation_type IN ('manual', 'schedule', 'auto')),
                    lux REAL,
                    solar_rad REAL,
                    altitude REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE daily_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    failure_count INTEGER DEFAULT 1,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "INSERT INTO operation_metrics (timestamp, date, action, operation_type)"
                " VALUES ('2026-01-01T07:00:00', '2026-01-01', 'open', 'manual')"
            )
            conn.commit()
            conn.close()
            yield db_path

    def test_migration_adds_shutter_columns(self, old_schema_db_path):
        """旧スキーマ DB に shutter 列が追加される"""
        import sqlite3

        import rasp_shutter.metrics.collector

        collector = rasp_shutter.metrics.collector.MetricsCollector(old_schema_db_path)

        conn = sqlite3.connect(old_schema_db_path)
        try:
            for table in ("operation_metrics", "daily_failures"):
                columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                assert "shutter_index" in columns, f"{table} に shutter_index がない"
                assert "shutter_name" in columns, f"{table} に shutter_name がない"
        finally:
            conn.close()

        # マイグレーション後に shutter 情報付きの INSERT が成功する
        collector.record_shutter_operation(
            action="open", mode="manual", shutter_index=0, shutter_name="リビング①"
        )
        collector.record_failure(shutter_index=1, shutter_name="リビング②")

        metrics = collector.get_all_operation_metrics()
        assert len(metrics) == 2
        # 旧データは shutter 列が NULL のまま
        assert metrics[0]["shutter_index"] is None
        assert metrics[0]["shutter_name"] is None
        assert metrics[1]["shutter_index"] == 0
        assert metrics[1]["shutter_name"] == "リビング①"

        failures = collector.get_all_failure_metrics()
        assert failures[0]["shutter_index"] == 1
        assert failures[0]["shutter_name"] == "リビング②"


class TestSensorSampleCleanup:
    """センサーサンプルのクリーンアップのテスト"""

    @pytest.fixture
    def temp_metrics_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield pathlib.Path(tmpdir) / "test_metrics.db"

    def test_cleanup_old_sensor_samples(self, temp_metrics_path):
        """保持期間を過ぎたサンプルのみが削除される"""
        import my_lib.time

        import rasp_shutter.metrics.collector
        from tests.fixtures.sensor_factory import SensorDataFactory

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)
        sensor_data = SensorDataFactory.custom(solar_rad=100, lux=500, altitude=10)

        now = my_lib.time.now()
        old_timestamp = now - datetime.timedelta(
            days=rasp_shutter.metrics.collector.SENSOR_SAMPLE_RETENTION_DAYS + 10
        )
        # NOTE: record_sensor_sample は日付が変わると自動クリーンアップを行うため、
        # 新しいサンプル → 古いサンプルの順に記録して自動削除を回避する
        collector.record_sensor_sample(sensor_data, context="auto_open_window", timestamp=now)
        collector.record_sensor_sample(sensor_data, context="off_hours", timestamp=old_timestamp)

        deleted = collector.cleanup_old_sensor_samples()
        assert deleted == 1

        samples = collector.get_recent_sensor_samples(1)
        assert len(samples) == 1
        assert samples[0]["context"] == "auto_open_window"


class TestShutterCounts:
    """シャッター個体別集計クエリのテスト"""

    @pytest.fixture
    def temp_metrics_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield pathlib.Path(tmpdir) / "test_metrics.db"

    def test_get_shutter_operation_counts(self, temp_metrics_path):
        """個体別の操作回数集計（NULL 個体混在）"""
        import rasp_shutter.metrics.collector

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)
        collector.record_shutter_operation(
            action="open", mode="manual", shutter_index=0, shutter_name="リビング①"
        )
        collector.record_shutter_operation(
            action="open", mode="manual", shutter_index=0, shutter_name="リビング①"
        )
        collector.record_shutter_operation(
            action="close", mode="auto", shutter_index=1, shutter_name="リビング②"
        )
        # NULL 個体（マイグレーション前相当）
        collector.record_shutter_operation(action="open", mode="schedule")

        counts = collector.get_shutter_operation_counts()

        def find(index, action, op_type):
            return next(
                (
                    row
                    for row in counts
                    if row["shutter_index"] == index
                    and row["action"] == action
                    and row["operation_type"] == op_type
                ),
                None,
            )

        manual_open = find(0, "open", "manual")
        assert manual_open is not None
        assert manual_open["count"] == 2
        assert manual_open["shutter_name"] == "リビング①"

        auto_close = find(1, "close", "auto")
        assert auto_close is not None
        assert auto_close["count"] == 1

        null_open = find(None, "open", "schedule")
        assert null_open is not None
        assert null_open["count"] == 1
        assert null_open["shutter_name"] is None

    def test_get_shutter_failure_counts(self, temp_metrics_path):
        """個体別の失敗回数集計（NULL 個体混在）"""
        import rasp_shutter.metrics.collector

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)
        collector.record_failure(shutter_index=0, shutter_name="リビング①")
        collector.record_failure(shutter_index=0, shutter_name="リビング①")
        collector.record_failure()

        counts = collector.get_shutter_failure_counts()
        by_index = {row["shutter_index"]: row for row in counts}
        assert by_index[0]["count"] == 2
        assert by_index[0]["shutter_name"] == "リビング①"
        assert by_index[None]["count"] == 1

    def test_get_daily_failure_counts(self, temp_metrics_path):
        """日別の失敗件数集計"""
        import rasp_shutter.metrics.collector

        collector = rasp_shutter.metrics.collector.MetricsCollector(temp_metrics_path)
        day1 = datetime.datetime(2026, 1, 1, 10, 0, 0)
        day2 = datetime.datetime(2026, 1, 2, 10, 0, 0)
        collector.record_failure(timestamp=day1)
        collector.record_failure(timestamp=day1)
        collector.record_failure(timestamp=day2)

        counts = collector.get_daily_failure_counts("2026-01-01", "2026-01-02")
        assert counts == [
            {"date": "2026-01-01", "count": 2},
            {"date": "2026-01-02", "count": 1},
        ]

        # 範囲外は含まれない
        counts_day1_only = collector.get_daily_failure_counts("2026-01-01", "2026-01-01")
        assert counts_day1_only == [{"date": "2026-01-01", "count": 2}]


class TestShutterStatistics:
    """generate_shutter_statistics のテスト"""

    def test_generate_shutter_statistics(self):
        """個体別統計の集計と schedule/auto の合算"""
        import rasp_shutter.metrics.analyzer

        operation_counts = [
            {
                "shutter_index": 0,
                "shutter_name": "リビング①",
                "action": "open",
                "operation_type": "manual",
                "count": 2,
            },
            {
                "shutter_index": 0,
                "shutter_name": "リビング①",
                "action": "open",
                "operation_type": "schedule",
                "count": 3,
            },
            {
                "shutter_index": 0,
                "shutter_name": "リビング①",
                "action": "open",
                "operation_type": "auto",
                "count": 4,
            },
            {
                "shutter_index": 0,
                "shutter_name": "リビング①",
                "action": "close",
                "operation_type": "auto",
                "count": 5,
            },
        ]
        failure_counts = [{"shutter_index": 0, "shutter_name": "リビング①", "count": 7}]

        result = rasp_shutter.metrics.analyzer.generate_shutter_statistics(operation_counts, failure_counts)

        assert len(result) == 1
        entry = result[0]
        assert entry["shutter_index"] == 0
        assert entry["shutter_name"] == "リビング①"
        assert entry["manual_open"] == 2
        assert entry["manual_close"] == 0
        # schedule + auto が auto_open に合算される
        assert entry["auto_open"] == 7
        assert entry["auto_close"] == 5
        assert entry["operation_total"] == 14
        assert entry["failure_total"] == 7

    def test_generate_shutter_statistics_null_last(self):
        """NULL 個体は末尾に配置され name は None のまま"""
        import rasp_shutter.metrics.analyzer

        operation_counts = [
            {
                "shutter_index": None,
                "shutter_name": None,
                "action": "open",
                "operation_type": "manual",
                "count": 1,
            },
            {
                "shutter_index": 1,
                "shutter_name": "リビング②",
                "action": "open",
                "operation_type": "manual",
                "count": 1,
            },
            {
                "shutter_index": 0,
                "shutter_name": "リビング①",
                "action": "open",
                "operation_type": "manual",
                "count": 1,
            },
        ]

        result = rasp_shutter.metrics.analyzer.generate_shutter_statistics(operation_counts, [])

        assert [entry["shutter_index"] for entry in result] == [0, 1, None]
        assert result[-1]["shutter_name"] is None


class TestFailureTimeSeries:
    """prepare_failure_time_series のテスト"""

    def test_prepare_failure_time_series(self):
        import rasp_shutter.metrics.analyzer

        daily_counts = [
            {"date": "2026-01-01", "count": 2},
            {"date": "2026-01-03", "count": 1},
        ]

        result = rasp_shutter.metrics.analyzer.prepare_failure_time_series(daily_counts)

        assert result == {"dates": ["2026-01-01", "2026-01-03"], "counts": [2, 1]}

    def test_prepare_failure_time_series_empty(self):
        import rasp_shutter.metrics.analyzer

        result = rasp_shutter.metrics.analyzer.prepare_failure_time_series([])

        assert result == {"dates": [], "counts": []}


class TestPostponeEventsTable:
    """prepare_postpone_events_table のテスト"""

    @staticmethod
    def _event(timestamp, resolved_at=None):
        return {
            "timestamp": timestamp,
            "date": timestamp[:10],
            "intended_action": "open",
            "trigger": "schedule",
            "scheduled_time": None,
            "reason": "too_dark",
            "lux": 100.0,
            "solar_rad": 50.0,
            "altitude": 10.0,
            "resolved_at": resolved_at,
        }

    def test_descending_order_and_lag(self):
        """新しい順に並び、resolved_at があれば lag_minutes を含む"""
        import rasp_shutter.metrics.analyzer

        events = [
            self._event("2026-01-01T07:00:00", resolved_at="2026-01-01T07:30:00"),
            self._event("2026-01-02T07:00:00"),
        ]

        result = rasp_shutter.metrics.analyzer.prepare_postpone_events_table(events)

        assert len(result) == 2
        assert result[0]["timestamp"] == "2026-01-02T07:00:00"
        assert result[0]["lag_minutes"] is None
        assert result[1]["timestamp"] == "2026-01-01T07:00:00"
        assert result[1]["lag_minutes"] == pytest.approx(30.0)

    def test_limit(self):
        """limit 件数で切り詰められる"""
        import rasp_shutter.metrics.analyzer

        events = [self._event(f"2026-01-01T07:{i:02d}:00") for i in range(10)]

        result = rasp_shutter.metrics.analyzer.prepare_postpone_events_table(events, limit=3)

        assert len(result) == 3
        # 新しい順（07:09 → 07:07）
        assert result[0]["timestamp"] == "2026-01-01T07:09:00"
        assert result[2]["timestamp"] == "2026-01-01T07:07:00"

    def test_default_limit_constant(self):
        """デフォルトの limit は POSTPONE_TABLE_LIMIT"""
        import rasp_shutter.metrics.analyzer

        events = [
            self._event(f"2026-01-01T{7 + i // 60:02d}:{i % 60:02d}:00")
            for i in range(rasp_shutter.metrics.analyzer.POSTPONE_TABLE_LIMIT + 20)
        ]

        result = rasp_shutter.metrics.analyzer.prepare_postpone_events_table(events)

        assert len(result) == rasp_shutter.metrics.analyzer.POSTPONE_TABLE_LIMIT


class TestThresholdTuning:
    """analyze_threshold_tuning のテスト"""

    @staticmethod
    def _too_dark_open_event(**kwargs):
        event = {
            "timestamp": "2026-01-01T07:00:00",
            "date": "2026-01-01",
            "intended_action": "open",
            "trigger": "schedule",
            "reason": "too_dark",
            "lux": 500.0,
            "solar_rad": 100.0,
            "altitude": 20.0,
            "threshold_lux": 1000.0,
            "threshold_solar_rad": 200.0,
            "threshold_altitude": 10.0,
            "resolved_at": None,
        }
        event.update(kwargs)
        return event

    @staticmethod
    def _schedule():
        return {
            "open": {"lux": 1000, "solar_rad": 200, "altitude": 10},
            "close": {"lux": 500, "solar_rad": 100, "altitude": 5},
        }

    def test_what_if_and_condition(self):
        """lux は足りるが solar_rad 不足のイベントは scale 1.0 で 0 件、緩和で数えられる"""
        import rasp_shutter.metrics.analyzer

        # lux: 1500 > 1000 (充足), solar_rad: 150 < 200 (不足), altitude: 20 > 10 (充足)
        event = self._too_dark_open_event(lux=1500.0, solar_rad=150.0, altitude=20.0)

        result = rasp_shutter.metrics.analyzer.analyze_threshold_tuning([event], self._schedule())

        what_if = {entry["scale"]: entry for entry in result["what_if"]}
        # scale 1.0: solar_rad 150 < 200 → AND 条件を満たさない
        assert what_if[1.0]["immediate_open_count"] == 0
        assert what_if[1.0]["total_events"] == 1
        assert what_if[1.0]["ratio"] == 0.0
        # scale 0.7: solar_rad 150 > 140, lux 1500 > 700 → 満たす
        assert what_if[0.7]["immediate_open_count"] == 1
        assert what_if[0.7]["ratio"] == pytest.approx(1.0)

    def test_what_if_altitude_not_scaled(self):
        """altitude は緩和されず現行スナップショット閾値のまま判定される"""
        import rasp_shutter.metrics.analyzer

        # lux/solar_rad は十分だが altitude が不足
        event = self._too_dark_open_event(lux=2000.0, solar_rad=300.0, altitude=5.0)

        result = rasp_shutter.metrics.analyzer.analyze_threshold_tuning([event], self._schedule())

        for entry in result["what_if"]:
            assert entry["immediate_open_count"] == 0

    def test_shortfall_distribution(self):
        """shortfall は閾値までの不足量の分布を返す（None は除外）"""
        import rasp_shutter.metrics.analyzer

        events = [
            self._too_dark_open_event(lux=600.0, solar_rad=150.0),
            self._too_dark_open_event(lux=None, solar_rad=180.0),
            # close イベントは対象外
            self._too_dark_open_event(intended_action="close"),
            # too_dark 以外は対象外
            self._too_dark_open_event(reason="sensor_invalid"),
        ]

        result = rasp_shutter.metrics.analyzer.analyze_threshold_tuning(events, self._schedule())

        assert result["shortfall"]["lux"] == [pytest.approx(400.0)]
        assert sorted(result["shortfall"]["solar_rad"]) == [pytest.approx(20.0), pytest.approx(50.0)]

    def test_resolve_lag_minutes(self):
        """解消された open イベントのラグ（分）を返す"""
        import rasp_shutter.metrics.analyzer

        events = [
            self._too_dark_open_event(resolved_at="2026-01-01T07:45:00"),
            self._too_dark_open_event(timestamp="2026-01-02T07:00:00", date="2026-01-02"),
        ]

        result = rasp_shutter.metrics.analyzer.analyze_threshold_tuning(events, self._schedule())

        assert result["resolve_lag_minutes"] == [pytest.approx(45.0)]

    def test_current_schedule_none(self):
        """current_schedule が None の場合は空構造を返す"""
        import rasp_shutter.metrics.analyzer

        result = rasp_shutter.metrics.analyzer.analyze_threshold_tuning([self._too_dark_open_event()], None)

        assert result == {
            "shortfall": {"lux": [], "solar_rad": []},
            "what_if": [],
            "resolve_lag_minutes": [],
        }


class TestSensorSamplesData:
    """prepare_sensor_samples_data のテスト"""

    def test_context_grouping(self):
        """context 別にグルーピングされ、NULL は unknown に分類される"""
        import rasp_shutter.metrics.analyzer

        samples = [
            {
                "timestamp": "2026-01-01T07:30:00",
                "lux": 100.0,
                "solar_rad": 50.0,
                "altitude": 10.0,
                "context": "auto_open_window",
            },
            {
                "timestamp": "2026-01-01T17:00:00",
                "lux": 200.0,
                "solar_rad": 60.0,
                "altitude": 20.0,
                "context": "auto_close_window",
            },
            {
                "timestamp": "2026-01-01T03:00:00",
                "lux": 0.0,
                "solar_rad": 0.0,
                "altitude": -30.0,
                "context": "off_hours",
            },
            {
                "timestamp": "2026-01-01T12:00:00",
                "lux": 5000.0,
                "solar_rad": 500.0,
                "altitude": 60.0,
                "context": None,
            },
        ]

        result = rasp_shutter.metrics.analyzer.prepare_sensor_samples_data(samples, None)

        assert result["sample_count"] == 4
        lux_series = result["series"]["lux"]
        assert lux_series["auto_open_window"] == [{"x": 7 * 60 + 30, "y": 100.0}]
        assert lux_series["auto_close_window"] == [{"x": 17 * 60, "y": 200.0}]
        assert lux_series["off_hours"] == [{"x": 3 * 60, "y": 0.0}]
        # NULL context は unknown
        assert lux_series["unknown"] == [{"x": 12 * 60, "y": 5000.0}]
        assert result["series"]["altitude"]["unknown"] == [{"x": 12 * 60, "y": 60.0}]

    def test_thresholds_from_schedule(self):
        """current_schedule から閾値が抽出される"""
        import rasp_shutter.metrics.analyzer

        schedule = {
            "open": {"lux": 1000, "solar_rad": 200, "altitude": 10},
            "close": {"lux": 500, "solar_rad": 100, "altitude": 5},
        }

        result = rasp_shutter.metrics.analyzer.prepare_sensor_samples_data([], schedule)

        assert result["sample_count"] == 0
        assert result["thresholds"]["lux"] == {"open": 1000.0, "close": 500.0}
        assert result["thresholds"]["altitude"] == {"open": 10.0, "close": 5.0}

    def test_none_value_excluded(self):
        """センサー値が None の系列には追加されない"""
        import rasp_shutter.metrics.analyzer

        samples = [
            {
                "timestamp": "2026-01-01T07:00:00",
                "lux": None,
                "solar_rad": 50.0,
                "altitude": 10.0,
                "context": "auto_open_window",
            },
        ]

        result = rasp_shutter.metrics.analyzer.prepare_sensor_samples_data(samples, None)

        assert result["series"]["lux"]["auto_open_window"] == []
        assert result["series"]["solar_rad"]["auto_open_window"] == [{"x": 7 * 60, "y": 50.0}]
