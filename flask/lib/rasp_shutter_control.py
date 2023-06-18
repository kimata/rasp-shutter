# -*- coding: utf-8 -*-
# #!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import request, jsonify, Blueprint, current_app
from enum import IntEnum

import requests
import time

from webapp_config import APP_URL_PREFIX, STAT_EXEC
from webapp_log import app_log, APP_LOG_LEVEL
from flask_util import support_jsonp, remote_host


# 自動で開けたり閉めたりする間隔．この時間内に再度自動で同じ制御がリクエストされた場合，
# 実行をやめる．
EXEC_INTERVAL_HOUR = 12


class SHUTTER_STATE(IntEnum):
    OPEN = 0
    CLOSE = 1
    UNKNOWN = 2


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


def call_shutter_api(config, mode):
    result = True
    for shutter in config["shutter"]:
        if requests.get(shutter["endpoint"][mode]).status_code != 200:
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


# auto = 0: 手動, 1: 自動(実際には制御しなかった場合にメッセージ有り), 2: 自動(実際に制御した場合のみメッセージ)
def set_shutter_state(state, auto, host=""):
    import logging

    logging.info(state)
    exec_hist = STAT_EXEC[state]
    if auto != 0:
        if exec_hist.exists() and (
            (time.time() - exec_hist.stat().st_mtime) / (60 * 60) < EXEC_INTERVAL_HOUR
        ):
            if auto == 1:
                diff_sec = time.time() - exec_hist.stat().st_mtime
                app_log(
                    (
                        "🔔 シャッターを自動で{done}るのを見合わせました．"
                        + "{time_diff_str}前に{done}ています．{by}"
                    ).format(
                        done="開け" if state == "open" else "閉め",
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
            "シャッターを{auto}で{done}ました．{by}".format(
                auto="🕑 自動" if auto > 0 else "🔧 手動",
                done="開け" if state == "open" else "閉め",
                by="(by {})".format(host) if host != "" else "",
            )
        )
    else:
        app_log(
            "シャッターを{auto}で{done}るのに失敗しました．{by}".format(
                auto="🕑 自動" if auto > 0 else "🔧 手動",
                done="開け" if state == "open" else "閉め",
                by="(by {})".format(host) if host != "" else "",
            ),
            APP_LOG_LEVEL.ERROR,
        )

    return get_shutter_state()


@blueprint.route("/api/shutter_ctrl", methods=["GET", "POST"])
@support_jsonp
def api_shutter_ctrl():
    cmd = request.args.get("cmd", 0, type=int)
    state = request.args.get("state", "close", type=str)
    auto = request.args.get("auto", False, type=bool)

    if cmd == 1:
        return jsonify(
            dict({"cmd": "set"}, **set_shutter_state(state, auto, remote_host(request)))
        )
    else:
        return jsonify(dict({"cmd": "get"}, **get_shutter_state()))


@blueprint.route("/api/dummy/open", methods=["GET"])
@support_jsonp
def api_dummy_open():
    return jsonify({"status": "OK"})


@blueprint.route("/api/dummy/close", methods=["GET"])
@support_jsonp
def api_dummy_close():
    return jsonify({"status": "OK"})
