#!/usr/bin/env python3

import datetime
import logging

import flask
import my_lib.time
import time_machine

import rasp_shutter.util

blueprint = flask.Blueprint("rasp-shutter-test-time", __name__)


# テスト用の時刻モック状態を保持
# NOTE: _traveler は time_machine.travel() のコンテキスト、_traveller は
# start() が返すオブジェクトで、稼働中の時刻変更（move_to / shift）に使う。
# traveler を stop() して作り直す方式だと、stop() から start() までの間に
# スケジューラスレッドが実時刻を観測し、schedule ライブラリのジョブ登録
# （next_run 計算）が実時刻基準で行われてジョブが発火しなくなるレースがある。
_traveler = None
_traveller = None


@blueprint.route("/api/test/time/set/<timestamp>", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def set_mock_time(timestamp):
    """
    テスト用時刻を設定するAPI

    Args:
        timestamp: Unix timestamp (秒) またはISO形式の日時文字列

    Returns:
        JSON: 設定された時刻情報

    """
    global _traveler, _traveller

    try:
        # タイムスタンプの解析
        if timestamp.isdigit():
            mock_datetime = datetime.datetime.fromtimestamp(int(timestamp), tz=my_lib.time.get_zoneinfo())
        else:
            # ISO形式の解析
            mock_datetime = datetime.datetime.fromisoformat(timestamp)
            if mock_datetime.tzinfo is None:
                mock_datetime = mock_datetime.replace(tzinfo=my_lib.time.get_zoneinfo())

        if _traveller is not None:
            # NOTE: 稼働中の traveler は停止せず move_to() で時刻を切り替える。
            # stop()/start() の再作成では、その間に実時刻が露出するレースがある。
            _traveller.move_to(mock_datetime)
        else:
            _traveler = time_machine.travel(mock_datetime)
            _traveller = _traveler.start()

        logging.info("Mock time set to: %s", mock_datetime)

        return {
            "success": True,
            "mock_time": mock_datetime.isoformat(),
            "unix_timestamp": int(mock_datetime.timestamp()),
        }

    except (ValueError, TypeError) as e:
        return {"error": f"Invalid timestamp format: {e}"}, 400


@blueprint.route("/api/test/time/advance/<int:seconds>", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def advance_mock_time(seconds):
    """
    モック時刻を指定秒数進める

    Args:
        seconds: 進める秒数

    Returns:
        JSON: 更新された時刻情報

    """
    if _traveller is None:
        return {"error": "Mock time not set. Use /api/test/time/set first"}, 400

    # NOTE: shift() で時刻を進める。traveler を stop()/start() で再作成すると、
    # その間に実時刻が露出し、同時に走っているスケジューラスレッドが
    # ジョブ登録や next_run 計算を実時刻基準で行ってしまうレースがある。
    _traveller.shift(datetime.timedelta(seconds=seconds))

    # NOTE: スケジュールの強制リロードは行わない。
    # 時刻を進めた後にスケジュールをリロードすると、Python schedule ライブラリが
    # 既に過ぎた時刻のジョブを「明日」にスケジュールしてしまう。
    # 既存のジョブはそのまま維持し、scheduler.run_pending() で評価させる。

    current_time = my_lib.time.now()
    logging.info("Mock time advanced to: %s", current_time)

    return {
        "success": True,
        "mock_time": current_time.isoformat(),
        "unix_timestamp": int(current_time.timestamp()),
        "advanced_seconds": seconds,
    }


@blueprint.route("/api/test/time/reset", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def reset_mock_time():
    """
    モック時刻をリセットして実際の時刻に戻す

    Returns:
        JSON: リセット結果

    """
    global _traveler, _traveller

    if _traveler:
        _traveler.stop()
        _traveler = None
        _traveller = None

    logging.info("Mock time reset to real time")

    return {"success": True, "real_time": my_lib.time.now().isoformat()}


@blueprint.route("/api/test/time/current", methods=["GET"])
@rasp_shutter.util.require_dummy_mode
def get_current_time():
    """
    現在の時刻（モック時刻または実時刻）を取得

    Returns:
        JSON: 現在時刻情報

    """
    current_time = my_lib.time.now()

    return {
        "current_time": current_time.isoformat(),
        "unix_timestamp": int(current_time.timestamp()),
        "is_mocked": _traveler is not None,
        "mock_time": current_time.isoformat() if _traveler else None,
    }
