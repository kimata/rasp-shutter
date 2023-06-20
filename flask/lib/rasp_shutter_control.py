# -*- coding: utf-8 -*-
# #!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import request, jsonify, Blueprint, current_app
from enum import IntEnum, Enum

import logging
import requests
import time

from webapp_config import APP_URL_PREFIX, STAT_EXEC, STAT_PENDING_OPEN, STAT_AUTO_CLOSE
from webapp_log import app_log, APP_LOG_LEVEL
from flask_util import support_jsonp, remote_host, set_acao


# 自動で開けたり閉めたりする間隔．この時間内に再度自動で同じ制御がリクエストされた場合，
# 実行をやめる．
EXEC_INTERVAL_HOUR = 12


class SHUTTER_STATE(IntEnum):
    OPEN = 0
    CLOSE = 1
    UNKNOWN = 2


class CONTROL_MODE(Enum):
    MANUAL = "🔧手動"
    SCHEDULE = "⏰スケジューラ"
    AUTO = "🤖自動"


blueprint = Blueprint("rasp-shutter-control", __name__, url_prefix=APP_URL_PREFIX)

config = None
should_terminate = False


@blueprint.before_app_first_request
def init():
    global config

    config = current_app.config["CONFIG"]

    STAT_EXEC["open"].parent.mkdir(parents=True, exist_ok=True)
    STAT_EXEC["close"].parent.mkdir(parents=True, exist_ok=True)


def minute_str(sec):
    min = sec / 60
    hour = 0
    if min >= 60:
        hour = int(min / 60)
        min -= hour * 60
    min = int(min)

    if hour != 0:
        if min == 0:
            return "{hour}時間".format(hour=hour)
        else:
            return "{hour}時間{min}分".format(hour=hour, min=min)
    else:
        return "{min}分".format(min=min)


def call_shutter_api(config, state):
    result = True
    for shutter in config["shutter"]:
        if requests.get(shutter["endpoint"][state]).status_code != 200:
            result = False

    return result


def get_shutter_state():
    state = None
    if STAT_EXEC["open"].exists():
        if STAT_EXEC["close"].exists():
            if STAT_EXEC["open"].stat().st_mtime > STAT_EXEC["close"].stat().st_mtime:
                state = SHUTTER_STATE.OPEN
            else:
                state = SHUTTER_STATE.CLOSE
        else:
            state = SHUTTER_STATE.OPEN
    else:
        if STAT_EXEC["close"].exists():
            state = SHUTTER_STATE.CLOSE
        else:
            state = SHUTTER_STATE.UNKNOWN

    return {
        "state": state.value,
        "result": "success",
    }


def set_shutter_state(state, mode, host=""):
    if state == "open":
        if mode != CONTROL_MODE.MANUAL:
            # NOTE: 手動以外でシャッターを開けた場合は，
            # 自動で閉じた履歴を削除する．
            STAT_AUTO_CLOSE.unlink(missing_ok=True)
    else:
        # NOTE: シャッターを閉じる指示がされた場合は，
        # 暗くて延期されていた開ける制御を取り消す．
        STAT_PENDING_OPEN.unlink(missing_ok=True)

    # NOTE: 閉じている場合に再度閉じるボタンをおしたり，逆に開いている場合に再度
    # 開くボタンを押すことが続くと，スイッチがエラーになるので STAT_EXEC を使って
    # 防止する．STAT_EXEC はこれ以外の目的で使わない．
    exec_hist = STAT_EXEC[state]
    if mode != CONTROL_MODE.MANUAL:
        if exec_hist.exists() and (
            (time.time() - exec_hist.stat().st_mtime) / (60 * 60) < EXEC_INTERVAL_HOUR
        ):
            if mode == CONTROL_MODE.SCHEDULE:
                # NOTE: スケジュール実行通りに制御できなかった場合，
                # ログを残す．
                diff_sec = time.time() - exec_hist.stat().st_mtime
                app_log(
                    (
                        "🔔 スケジュールに従ってシャッターを{state}るのを見合わせました。"
                        + "{time_diff_str}前に{done}ています。{by}"
                    ).format(
                        state="開け" if state == "open" else "閉め",
                        time_diff_str=minute_str(diff_sec),
                        by="(by {})".format(host) if host != "" else "",
                    )
                )
            return get_shutter_state()
    exec_hist.touch()

    exec_inv_hist = STAT_EXEC["close" if state == "open" else "open"]
    exec_inv_hist.unlink(missing_ok=True)

    result = call_shutter_api(config, state)

    if result:
        app_log(
            "シャッターを{mode}で{state}ました。{by}".format(
                mode=mode.value,
                state="開け" if state == "open" else "閉め",
                by="(by {})".format(host) if host != "" else "",
            )
        )
    else:
        app_log(
            "シャッターを{mode}で{state}るのに失敗しました。{by}".format(
                mode=mode.value,
                state="開け" if state == "open" else "閉め",
                by="(by {})".format(host) if host != "" else "",
            ),
            APP_LOG_LEVEL.ERROR,
        )

    return get_shutter_state()


@blueprint.route("/api/shutter_ctrl", methods=["GET", "POST"])
@support_jsonp
@set_acao
def api_shutter_ctrl():
    cmd = request.args.get("cmd", 0, type=int)
    state = request.args.get("state", "close", type=str)

    if cmd == 1:
        return jsonify(
            dict(
                {"cmd": "set"},
                **set_shutter_state(state, CONTROL_MODE.MANUAL, remote_host(request))
            )
        )
    else:
        return jsonify(dict({"cmd": "get"}, **get_shutter_state()))


@blueprint.route("/api/dummy/open", methods=["GET"])
@support_jsonp
@set_acao
def api_dummy_open():
    logging.info("ダミーのシャッターが開きました．")
    return jsonify({"status": "OK"})


@blueprint.route("/api/dummy/close", methods=["GET"])
@support_jsonp
@set_acao
def api_dummy_close():
    logging.info("ダミーのシャッターが閉じました．")
    return jsonify({"status": "OK"})
