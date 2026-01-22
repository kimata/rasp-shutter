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
