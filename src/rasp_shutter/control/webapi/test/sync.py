#!/usr/bin/env python3
"""テスト同期用API

テストでの非同期処理の同期化を支援するAPIを提供します。
"""

import logging
import threading
import time

import flask
import my_lib.footprint
import my_lib.notify.slack
import my_lib.time
import my_lib.webapp.config

import rasp_shutter.control.config
import rasp_shutter.control.scheduler
import rasp_shutter.control.webapi.control
import rasp_shutter.util

blueprint = flask.Blueprint("rasp-shutter-test-sync", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)

# イベント管理用の辞書
_events: dict[str, threading.Event] = {}
_events_lock = threading.Lock()


def _get_event(event_name: str) -> threading.Event:
    """イベントを取得（存在しない場合は作成）"""
    with _events_lock:
        if event_name not in _events:
            _events[event_name] = threading.Event()
        return _events[event_name]


@blueprint.route("/api/test/sync/wait/<event_name>", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def wait_for_event(event_name: str):
    """
    イベントの完了を待機

    Args:
        event_name: イベント名

    Query Params:
        timeout: タイムアウト秒数（デフォルト: 30）

    Returns:
        JSON: 待機結果
    """
    # FlaskのTypeConversionDictの型定義が不完全なため抑制
    timeout = flask.request.args.get("timeout", 30, type=float)  # type: ignore[arg-type]

    event = _get_event(event_name)
    event.clear()  # 待機前にクリア

    logging.info("Waiting for event '%s' (timeout: %s sec)", event_name, timeout)

    if event.wait(timeout):
        logging.info("Event '%s' received", event_name)
        return {
            "success": True,
            "event": event_name,
            "received": True,
        }
    else:
        logging.warning("Timeout waiting for event '%s'", event_name)
        return {
            "success": False,
            "event": event_name,
            "received": False,
            "error": "Timeout waiting for event",
        }, 408


@blueprint.route("/api/test/sync/signal/<event_name>", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def signal_event(event_name: str):
    """
    イベント完了をシグナル

    Args:
        event_name: イベント名

    Returns:
        JSON: シグナル結果
    """
    event = _get_event(event_name)
    event.set()

    logging.info("Event '%s' signaled", event_name)

    return {
        "success": True,
        "event": event_name,
        "signaled": True,
    }


@blueprint.route("/api/test/sync/clear/<event_name>", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def clear_event(event_name: str):
    """
    イベントをクリア

    Args:
        event_name: イベント名

    Returns:
        JSON: クリア結果
    """
    event = _get_event(event_name)
    event.clear()

    logging.info("Event '%s' cleared", event_name)

    return {
        "success": True,
        "event": event_name,
        "cleared": True,
    }


@blueprint.route("/api/test/scheduler/state", methods=["GET"])
@rasp_shutter.util.require_dummy_mode
def get_scheduler_state():
    """
    スケジューラーの状態を取得

    Returns:
        JSON: スケジューラー状態
    """
    scheduler = rasp_shutter.control.scheduler.get_scheduler()
    schedule_data = rasp_shutter.control.scheduler.get_schedule_data()

    jobs = [
        {
            "next_run": job.next_run.isoformat() if job.next_run else None,
            # partialオブジェクトの場合__name__がないためgetattr使用
            "job_func": getattr(job.job_func, "__name__", str(job.job_func)) if job.job_func else None,
        }
        for job in scheduler.get_jobs()
    ]

    idle_sec = scheduler.idle_seconds

    return {
        "success": True,
        "current_time": my_lib.time.now().isoformat(),
        "idle_seconds": idle_sec,
        "job_count": len(jobs),
        "jobs": jobs,
        "schedule_data": schedule_data,
    }


@blueprint.route("/api/test/scheduler/trigger", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def trigger_scheduler():
    """
    スケジューラーのジョブを即座に実行

    Query Params:
        job_index: 実行するジョブのインデックス（省略時は全ジョブ）

    Returns:
        JSON: 実行結果
    """
    scheduler = rasp_shutter.control.scheduler.get_scheduler()

    job_index = flask.request.args.get("job_index", type=int)

    try:
        jobs = scheduler.get_jobs()

        if job_index is not None:
            if 0 <= job_index < len(jobs):
                jobs[job_index].run()
                return {
                    "success": True,
                    "executed_job": job_index,
                }
            else:
                return {"error": f"Invalid job index: {job_index}"}, 400

        # 全ジョブを実行
        executed = 0
        for job in jobs:
            job.run()
            executed += 1

        return {
            "success": True,
            "executed_jobs": executed,
        }

    except Exception as e:
        logging.exception("Error triggering scheduler")
        return {"error": str(e)}, 500


@blueprint.route("/api/test/scheduler/wait_auto_control", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def wait_auto_control():
    """
    自動制御の完了を待機

    Query Params:
        timeout: タイムアウト秒数（デフォルト: 30）

    Returns:
        JSON: 待機結果
    """
    timeout = flask.request.args.get("timeout", 30.0, type=float)

    success = rasp_shutter.control.scheduler.wait_for_auto_control_completion(timeout)

    return {
        "success": success,
        "completed": success,
    }


@blueprint.route("/api/test/scheduler/loop_sequence", methods=["GET"])
@rasp_shutter.util.require_dummy_mode
def get_loop_sequence():
    """
    現在のループシーケンス番号を取得

    Returns:
        JSON: シーケンス番号
    """
    import my_lib.pytest_util

    worker_id = my_lib.pytest_util.get_worker_id()
    sequence = rasp_shutter.control.scheduler.get_loop_sequence()

    logging.debug("get_loop_sequence: worker_id=%s, sequence=%d", worker_id, sequence)

    return {
        "success": True,
        "sequence": sequence,
        "worker_id": worker_id,
        "current_time": my_lib.time.now().isoformat(),
    }


@blueprint.route("/api/test/scheduler/wait_loop", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def wait_loop():
    """
    指定シーケンス番号より大きくなるまで待機

    Query Params:
        sequence: 待機開始時のシーケンス番号
        timeout: タイムアウト秒数（デフォルト: 10）

    Returns:
        JSON: 待機結果
    """
    sequence = flask.request.args.get("sequence", 0, type=int)
    timeout = flask.request.args.get("timeout", 10.0, type=float)

    success = rasp_shutter.control.scheduler.wait_for_loop_after(sequence, timeout)
    current_sequence = rasp_shutter.control.scheduler.get_loop_sequence()

    if success:
        return {
            "success": True,
            "waited": True,
            "start_sequence": sequence,
            "current_sequence": current_sequence,
            "current_time": my_lib.time.now().isoformat(),
        }
    else:
        return {
            "success": False,
            "waited": False,
            "start_sequence": sequence,
            "current_sequence": current_sequence,
            "error": "Timeout waiting for scheduler loop",
        }, 408


@blueprint.route("/api/test/state/shutter", methods=["GET"])
@rasp_shutter.util.require_dummy_mode
def get_shutter_state():
    """
    シャッターの詳細状態を取得

    Returns:
        JSON: シャッター状態
    """
    config = flask.current_app.config["CONFIG"]

    states = []
    for index, shutter in enumerate(config.shutter):
        open_elapsed = my_lib.footprint.elapsed(
            rasp_shutter.control.webapi.control.exec_stat_file("open", index)
        )
        close_elapsed = my_lib.footprint.elapsed(
            rasp_shutter.control.webapi.control.exec_stat_file("close", index)
        )

        states.append(
            {
                "index": index,
                "name": shutter.name if hasattr(shutter, "name") else f"shutter_{index}",
                "open_elapsed_sec": open_elapsed,
                "close_elapsed_sec": close_elapsed,
            }
        )

    pending_open = my_lib.footprint.exists(rasp_shutter.control.config.STAT_PENDING_OPEN.to_path())
    pending_open_elapsed = my_lib.footprint.elapsed(rasp_shutter.control.config.STAT_PENDING_OPEN.to_path())

    auto_close_elapsed = my_lib.footprint.elapsed(rasp_shutter.control.config.STAT_AUTO_CLOSE.to_path())

    return {
        "success": True,
        "current_time": my_lib.time.now().isoformat(),
        "shutters": states,
        "pending_open": pending_open,
        "pending_open_elapsed_sec": pending_open_elapsed,
        "auto_close_elapsed_sec": auto_close_elapsed,
    }


@blueprint.route("/api/test/state/reset", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def reset_test_state():
    """
    テスト状態をリセット

    Returns:
        JSON: リセット結果
    """
    config = flask.current_app.config["CONFIG"]

    # 制御統計をクリア
    rasp_shutter.control.webapi.control.clean_stat_exec(config)

    # 自動制御状態をクリア
    rasp_shutter.control.config.STAT_AUTO_CLOSE.unlink(missing_ok=True)
    rasp_shutter.control.config.STAT_PENDING_OPEN.unlink(missing_ok=True)

    # Slack通知履歴をクリア
    my_lib.notify.slack._interval_clear()
    my_lib.notify.slack._hist_clear()

    # 制御ログをクリア
    rasp_shutter.control.webapi.control.cmd_hist.clear()

    # イベントをクリア
    with _events_lock:
        for event in _events.values():
            event.clear()

    logging.info("Test state reset completed")

    return {
        "success": True,
        "message": "Test state reset completed",
    }


@blueprint.route("/api/ctrl/clear", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def clear_control_log():
    """
    制御ログをクリア（E2Eテスト用）

    Returns:
        JSON: クリア結果
    """
    rasp_shutter.control.webapi.control.cmd_hist.clear()

    return {
        "success": True,
        "message": "Control log cleared",
    }


@blueprint.route("/api/test/schedule/reset", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def reset_schedule():
    """
    スケジュールをリセット（E2Eテスト用）

    スケジューラのジョブとスケジュールデータをクリアして、
    テスト間の干渉を防ぐ。

    Returns:
        JSON: リセット結果
    """
    rasp_shutter.control.scheduler.clear_scheduler_jobs()

    logging.info("Schedule reset completed")

    return {
        "success": True,
        "message": "Schedule reset completed",
    }


@blueprint.route("/api/test/wait_condition", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def wait_condition():
    """
    条件が満たされるまで待機

    JSON Body:
        type: 条件タイプ ("ctrl_log_count", "app_log_count", "shutter_state")
        value: 期待値
        timeout: タイムアウト秒数

    Returns:
        JSON: 待機結果
    """
    data = flask.request.get_json()
    if not data:
        return {"error": "JSON body required"}, 400

    condition_type = data.get("type")
    expected_value = data.get("value")
    timeout = data.get("timeout", 10.0)

    if not condition_type or expected_value is None:
        return {"error": "type and value are required"}, 400

    # NOTE: time.perf_counter() を使用（time_machine の影響を受けない）
    start_time = time.perf_counter()
    poll_interval = 0.1
    current_value = None

    while time.perf_counter() - start_time < timeout:
        if condition_type == "ctrl_log_count":
            current_value = len(rasp_shutter.control.webapi.control.cmd_hist)
        elif condition_type == "shutter_state":
            # TODO: シャッター状態のチェック実装
            current_value = None
        else:
            current_value = None

        if current_value is not None and current_value >= expected_value:
            return {
                "success": True,
                "condition_met": True,
                "current_value": current_value,
                "elapsed_sec": time.perf_counter() - start_time,
            }

        time.sleep(poll_interval)

    return {
        "success": False,
        "condition_met": False,
        "current_value": current_value,
        "elapsed_sec": timeout,
        "error": "Timeout waiting for condition",
    }, 408
