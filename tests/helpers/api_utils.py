#!/usr/bin/env python3
# ruff: noqa: S101
"""API呼び出しヘルパー

シャッター制御、スケジュール、ログなどのAPI呼び出しを簡略化するヘルパークラスを提供します。
"""

import json
from typing import TYPE_CHECKING, Any

import my_lib.webapp.config

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def _get_json(response) -> dict[str, Any]:
    """レスポンスからJSONを取得してNoneチェック"""
    result = response.json
    assert result is not None, "Response JSON is None"
    return result


class ShutterAPI:
    """シャッター制御APIヘルパー"""

    def __init__(self, client: "FlaskClient"):
        self.client = client
        self.url_prefix = my_lib.webapp.config.URL_PREFIX

    def open(self, index: int | None = None) -> dict[str, Any]:
        """シャッターを開く

        Args:
            index: シャッターのインデックス（Noneの場合は全シャッター）

        Returns:
            APIレスポンスのJSON
        """
        return self._control("open", index)

    def close(self, index: int | None = None) -> dict[str, Any]:
        """シャッターを閉じる

        Args:
            index: シャッターのインデックス（Noneの場合は全シャッター）

        Returns:
            APIレスポンスのJSON
        """
        return self._control("close", index)

    def get_state(self) -> dict[str, Any]:
        """シャッターの状態を取得

        Returns:
            APIレスポンスのJSON
        """
        response = self.client.get(f"{self.url_prefix}/api/shutter_ctrl")
        assert response.status_code == 200
        return _get_json(response)

    def get_list(self) -> dict[str, Any]:
        """シャッターリストを取得

        Returns:
            APIレスポンスのJSON
        """
        response = self.client.get(f"{self.url_prefix}/api/shutter_list")
        assert response.status_code == 200
        return _get_json(response)

    def _control(self, state: str, index: int | None = None) -> dict[str, Any]:
        """シャッター制御の内部メソッド

        Args:
            state: "open" または "close"
            index: シャッターのインデックス

        Returns:
            APIレスポンスのJSON
        """
        query: dict[str, Any] = {"cmd": 1, "state": state}
        if index is not None:
            query["index"] = index

        response = self.client.get(
            f"{self.url_prefix}/api/shutter_ctrl",
            query_string=query,
        )
        assert response.status_code == 200
        result = _get_json(response)
        assert result["result"] == "success"
        return result


class ScheduleAPI:
    """スケジュール制御APIヘルパー"""

    def __init__(self, client: "FlaskClient"):
        self.client = client
        self.url_prefix = my_lib.webapp.config.URL_PREFIX

    def get(self) -> dict[str, Any]:
        """スケジュールを取得

        Returns:
            APIレスポンスのJSON
        """
        response = self.client.get(f"{self.url_prefix}/api/schedule_ctrl")
        assert response.status_code == 200
        return _get_json(response)

    def update(self, schedule_data: dict) -> dict[str, Any]:
        """スケジュールを更新

        Args:
            schedule_data: スケジュールデータ

        Returns:
            APIレスポンスのJSON
        """
        response = self.client.get(
            f"{self.url_prefix}/api/schedule_ctrl",
            query_string={"cmd": "set", "data": json.dumps(schedule_data)},
        )
        assert response.status_code == 200
        return _get_json(response)


class LogAPI:
    """ログAPIヘルパー"""

    def __init__(self, client: "FlaskClient"):
        self.client = client
        self.url_prefix = my_lib.webapp.config.URL_PREFIX

    def view(self) -> list:
        """ログを取得

        Returns:
            ログエントリのリスト
        """
        response = self.client.get(f"{self.url_prefix}/api/log_view")
        assert response.status_code in {200, 301}
        result = _get_json(response)
        return result.get("data", [])

    def clear(self) -> dict[str, Any]:
        """ログをクリア

        Returns:
            APIレスポンスのJSON
        """
        response = self.client.get(f"{self.url_prefix}/api/log_clear")
        assert response.status_code == 200
        return _get_json(response)

    def count(self) -> int:
        """ログ数を取得

        Returns:
            ログエントリ数
        """
        return len(self.view())


class CtrlLogAPI:
    """制御ログAPIヘルパー"""

    def __init__(self, client: "FlaskClient"):
        self.client = client
        self.url_prefix = my_lib.webapp.config.URL_PREFIX

    def get(self) -> list:
        """制御ログを取得

        Returns:
            制御ログエントリのリスト
        """
        response = self.client.get(f"{self.url_prefix}/api/ctrl/log")
        assert response.status_code == 200
        result = _get_json(response)
        assert result["result"] == "success"
        return result["log"]

    def clear(self) -> dict[str, Any]:
        """制御ログをクリア

        Returns:
            APIレスポンスのJSON
        """
        response = self.client.get(
            f"{self.url_prefix}/api/ctrl/log",
            query_string={"cmd": "clear"},
        )
        assert response.status_code == 200
        result = _get_json(response)
        assert result["result"] == "success"
        return result

    def count(self) -> int:
        """制御ログ数を取得

        Returns:
            制御ログエントリ数
        """
        return len(self.get())


class SensorAPI:
    """センサーAPIヘルパー"""

    def __init__(self, client: "FlaskClient"):
        self.client = client
        self.url_prefix = my_lib.webapp.config.URL_PREFIX

    def get(self) -> dict[str, Any]:
        """センサーデータを取得

        Returns:
            APIレスポンスのJSON
        """
        response = self.client.get(f"{self.url_prefix}/api/sensor")
        assert response.status_code == 200
        return _get_json(response)


class SystemAPI:
    """システム情報APIヘルパー"""

    def __init__(self, client: "FlaskClient"):
        self.client = client
        self.url_prefix = my_lib.webapp.config.URL_PREFIX

    def sysinfo(self) -> dict[str, Any]:
        """システム情報を取得

        Returns:
            APIレスポンスのJSON
        """
        response = self.client.get(f"{self.url_prefix}/api/sysinfo")
        assert response.status_code == 200
        return _get_json(response)

    def memory(self) -> dict[str, Any]:
        """メモリ情報を取得

        Returns:
            APIレスポンスのJSON
        """
        response = self.client.get(f"{self.url_prefix}/api/memory")
        assert response.status_code == 200
        return _get_json(response)

    def snapshot(self) -> dict[str, Any]:
        """スナップショットを取得

        Returns:
            APIレスポンスのJSON
        """
        response = self.client.get(f"{self.url_prefix}/api/snapshot")
        assert response.status_code == 200
        return _get_json(response)
