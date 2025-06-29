#!/usr/bin/env python3

import datetime
import logging
import os
from unittest.mock import patch

import my_lib.time

import flask

blueprint = flask.Blueprint("rasp-shutter-test-time", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)


# テスト用の時刻モック状態を保持
_mock_time = None
_time_patcher = None
_schedule_patcher = None


@blueprint.route("/api/test/time/set/<timestamp>", methods=["POST"])
def set_mock_time(timestamp):
    """
    テスト用時刻を設定するAPI

    Args:
        timestamp: Unix timestamp (秒) またはISO形式の日時文字列

    Returns:
        JSON: 設定された時刻情報

    """
    global _mock_time, _time_patcher, _schedule_patcher  # noqa: PLW0603

    # DUMMY_MODE でない場合は拒否
    if os.environ.get("DUMMY_MODE", "false") != "true":
        return {"error": "Test API is only available in DUMMY_MODE"}, 403

    try:
        # タイムスタンプの解析
        if timestamp.isdigit():
            mock_datetime = datetime.datetime.fromtimestamp(int(timestamp), tz=my_lib.time.get_zoneinfo())
        else:
            # ISO形式の解析
            mock_datetime = datetime.datetime.fromisoformat(timestamp)
            if mock_datetime.tzinfo is None:
                mock_datetime = mock_datetime.replace(tzinfo=my_lib.time.get_zoneinfo())

        _mock_time = mock_datetime

        # 既存のパッチャーがあれば停止
        if _time_patcher:
            _time_patcher.stop()
        if _schedule_patcher:
            _schedule_patcher.stop()

        # my_lib.time.now() を全体的にモック
        _time_patcher = patch("my_lib.time.now", return_value=_mock_time)
        _time_patcher.start()

        # スケジューラーモジュールでもパッチ
        _schedule_patcher = patch("rasp_shutter.scheduler.my_lib.time.now", return_value=_mock_time)
        _schedule_patcher.start()

        logging.info("Mock time set to: %s", _mock_time)

        return {
            "success": True,
            "mock_time": _mock_time.isoformat(),
            "unix_timestamp": int(_mock_time.timestamp()),
        }

    except (ValueError, TypeError) as e:
        return {"error": f"Invalid timestamp format: {e}"}, 400


@blueprint.route("/api/test/time/advance/<int:seconds>", methods=["POST"])
def advance_mock_time(seconds):
    """
    モック時刻を指定秒数進める

    Args:
        seconds: 進める秒数

    Returns:
        JSON: 更新された時刻情報

    """
    global _mock_time, _time_patcher, _schedule_patcher  # noqa: PLW0603

    # DUMMY_MODE でない場合は拒否
    if os.environ.get("DUMMY_MODE", "false") != "true":
        return {"error": "Test API is only available in DUMMY_MODE"}, 403

    if _mock_time is None:
        return {"error": "Mock time not set. Use /api/test/time/set first"}, 400

    _mock_time = _mock_time + datetime.timedelta(seconds=seconds)

    # パッチャーを更新
    if _time_patcher:
        _time_patcher.stop()
    if _schedule_patcher:
        _schedule_patcher.stop()

    _time_patcher = patch("my_lib.time.now", return_value=_mock_time)
    _time_patcher.start()

    _schedule_patcher = patch("rasp_shutter.scheduler.my_lib.time.now", return_value=_mock_time)
    _schedule_patcher.start()

    logging.info("Mock time advanced to: %s", _mock_time)

    return {
        "success": True,
        "mock_time": _mock_time.isoformat(),
        "unix_timestamp": int(_mock_time.timestamp()),
        "advanced_seconds": seconds,
    }


@blueprint.route("/api/test/time/reset", methods=["POST"])
def reset_mock_time():
    """
    モック時刻をリセットして実際の時刻に戻す

    Returns:
        JSON: リセット結果

    """
    global _mock_time, _time_patcher, _schedule_patcher  # noqa: PLW0603

    # DUMMY_MODE でない場合は拒否
    if os.environ.get("DUMMY_MODE", "false") != "true":
        return {"error": "Test API is only available in DUMMY_MODE"}, 403

    if _time_patcher:
        _time_patcher.stop()
        _time_patcher = None

    if _schedule_patcher:
        _schedule_patcher.stop()
        _schedule_patcher = None

    _mock_time = None

    logging.info("Mock time reset to real time")

    return {"success": True, "real_time": my_lib.time.now().isoformat()}


@blueprint.route("/api/test/time/current", methods=["GET"])
def get_current_time():
    """
    現在の時刻（モック時刻または実時刻）を取得

    Returns:
        JSON: 現在時刻情報

    """
    # DUMMY_MODE でない場合は拒否
    if os.environ.get("DUMMY_MODE", "false") != "true":
        return {"error": "Test API is only available in DUMMY_MODE"}, 403

    current_time = my_lib.time.now()

    return {
        "current_time": current_time.isoformat(),
        "unix_timestamp": int(current_time.timestamp()),
        "is_mocked": _mock_time is not None,
        "mock_time": _mock_time.isoformat() if _mock_time else None,
    }
