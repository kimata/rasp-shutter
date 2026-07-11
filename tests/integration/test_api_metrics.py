#!/usr/bin/env python3
# ruff: noqa: S101
"""メトリクスAPIの統合テスト"""

from tests.helpers.api_utils import MetricsAPI, ShutterAPI
from tests.helpers.time_utils import setup_midnight_time


class TestMetricsAPIAccess:
    """メトリクスAPI基本アクセステスト"""

    def test_metrics_page_empty_data(self, client, time_machine):
        """データが空の場合でもページは表示される"""
        setup_midnight_time(client, time_machine)

        metrics_api = MetricsAPI(client)
        status_code, body = metrics_api.get_page()

        # DBが存在すればページは表示される（空でもOK）
        # DBが存在しない場合は503になる
        assert status_code in {200, 503}
        if status_code == 200:
            assert "シャッター メトリクス ダッシュボード" in body

    def test_metrics_page_with_data(self, client, time_machine):
        """シャッター操作後、メトリクスページが表示される"""
        setup_midnight_time(client, time_machine)

        # シャッター操作を行ってメトリクスデータを生成
        shutter_api = ShutterAPI(client)
        shutter_api.open(index=0)
        shutter_api.close(index=0)

        metrics_api = MetricsAPI(client)
        status_code, body = metrics_api.get_page()

        # メトリクスページが正常に表示される
        assert status_code == 200
        assert "シャッター メトリクス ダッシュボード" in body
        assert "基本統計" in body


class TestMetricsPageContent:
    """メトリクスページコンテンツテスト"""

    def test_metrics_page_contains_statistics(self, client, time_machine):
        """メトリクスページに統計情報が含まれる"""
        setup_midnight_time(client, time_machine)

        # シャッター操作を行う
        shutter_api = ShutterAPI(client)
        shutter_api.open(index=0)
        shutter_api.close(index=0)

        metrics_api = MetricsAPI(client)
        status_code, body = metrics_api.get_page()

        assert status_code == 200
        # 基本的なセクションが含まれる
        assert "操作回数" in body
        assert "時刻分析" in body

    def test_metrics_page_reflects_operations(self, client, time_machine):
        """メトリクスページが操作回数を反映する"""
        setup_midnight_time(client, time_machine)

        # 複数回のシャッター操作を行う
        shutter_api = ShutterAPI(client)
        shutter_api.open(index=0)
        shutter_api.close(index=0)
        shutter_api.open(index=1)

        metrics_api = MetricsAPI(client)
        status_code, body = metrics_api.get_page()

        assert status_code == 200
        # ページが正常に生成されることを確認
        assert "手動開操作" in body
        assert "手動閉操作" in body

    def test_metrics_page_references_dashboard_js(self, client, time_machine):
        """メトリクスページに metrics-dashboard.js への参照が含まれる"""
        setup_midnight_time(client, time_machine)

        # DB を確実に作成するため操作を行う
        shutter_api = ShutterAPI(client)
        shutter_api.open(index=0)

        metrics_api = MetricsAPI(client)
        status_code, body = metrics_api.get_page()

        assert status_code == 200
        assert "metrics-dashboard.js" in body


class TestMetricsDataAPI:
    """メトリクスデータ API のテスト"""

    def test_metrics_data_top_level_keys(self, client, time_machine):
        """GET /api/metrics/data が 200 とトップレベルキーを返す"""
        setup_midnight_time(client, time_machine)

        # DB を確実に作成するため操作を行う
        shutter_api = ShutterAPI(client)
        shutter_api.open(index=0)

        metrics_api = MetricsAPI(client)
        status_code, data = metrics_api.get_data()

        assert status_code == 200
        for key in (
            "data_period",
            "stats",
            "shutter_breakdown",
            "postpone",
            "charts",
            "threshold_tuning",
            "reason_labels",
            "current_thresholds",
        ):
            assert key in data, f"トップレベルキー {key} がない"

        assert "summary" in data["postpone"]
        assert "chart" in data["postpone"]
        assert "events" in data["postpone"]
        for chart_key in (
            "open_times",
            "close_times",
            "auto_sensor_data",
            "manual_sensor_data",
            "time_series",
            "failure_time_series",
            "sensor_samples",
            "threshold_margin",
        ):
            assert chart_key in data["charts"], f"charts キー {chart_key} がない"

    def test_metrics_data_reflects_operations(self, client, time_machine, config):
        """操作後に stats.manual_open_total が増え、shutter_breakdown にシャッター名が現れる"""
        setup_midnight_time(client, time_machine)

        shutter_api = ShutterAPI(client)
        shutter_api.open(index=0)

        metrics_api = MetricsAPI(client)
        status_code, data_before = metrics_api.get_data()
        assert status_code == 200
        before_count = data_before["stats"]["manual_open_total"]

        # NOTE: 同方向の連続操作は制御間隔チェックで見合わせになるため、
        # 一度閉めてから再度開ける
        shutter_api.close(index=0)
        shutter_api.open(index=0)

        status_code, data_after = metrics_api.get_data()
        assert status_code == 200
        assert data_after["stats"]["manual_open_total"] == before_count + 1

        # shutter_breakdown に config のシャッター名が現れる
        shutter_names = [entry["shutter_name"] for entry in data_after["shutter_breakdown"]]
        assert config.shutter[0].name in shutter_names


class TestMetricsStaticFiles:
    """メトリクス静的ファイル配信のテスト"""

    def test_dashboard_js_served(self, client):
        """metrics-dashboard.js が配信される"""
        import rasp_shutter.config

        response = client.get(f"{rasp_shutter.config.URL_PREFIX}/metrics/static/js/metrics-dashboard.js")

        assert response.status_code == 200
        assert "initMetricsDashboard" in response.data.decode("utf-8")

    def test_charts_js_served(self, client):
        """metrics-charts.js が配信される"""
        import rasp_shutter.config

        response = client.get(f"{rasp_shutter.config.URL_PREFIX}/metrics/static/js/metrics-charts.js")

        assert response.status_code == 200
        assert "renderAllCharts" in response.data.decode("utf-8")
