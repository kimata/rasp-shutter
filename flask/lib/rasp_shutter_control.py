# -*- coding: utf-8 -*-
# #!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import request, jsonify, Blueprint, current_app
from flask_cors import cross_origin
from enum import IntEnum, Enum

import logging
import requests
import time
import os

from webapp_config import APP_URL_PREFIX, STAT_EXEC, STAT_PENDING_OPEN, STAT_AUTO_CLOSE
from webapp_log import app_log, APP_LOG_LEVEL
from flask_util import support_jsonp, remote_host


# この時間内に同じ制御がスケジューラで再度リクエストされた場合，
# 実行をやめる．
EXEC_INTERVAL_SCHEDULE_HOUR = 12
# この時間内に同じ制御がスケジューラで再度リクエストされた場合，
# 実行をやめる．
EXEC_INTERVAL_MANUAL_MINUTES = 1


class SHUTTER_STATE(IntEnum):
    OPEN = 0
    CLOSE = 1
    UNKNOWN = 2


class CONTROL_MODE(Enum):
    MANUAL = "🔧手動"
    SCHEDULE = "⏰スケジューラ"
    AUTO = "🤖自動"


blueprint = Blueprint("rasp-shutter-control", __name__, url_prefix=APP_URL_PREFIX)

should_terminate = False


def init():
    STAT_EXEC["open"].parent.mkdir(parents=True, exist_ok=True)
    STAT_EXEC["close"].parent.mkdir(parents=True, exist_ok=True)


def time_str(time_val):
    if time_val > (60 * 60):
        unit = ["分", "時間"]
        time_val /= 60
    else:
        unit = ["秒", "分"]

    upper = 0
    if time_val >= 60:
        upper = int(time_val / 60)
        time_val -= upper * 60
    time_val = int(time_val)

    if upper != 0:
        if time_val == 0:
            return "{upper}{unit_1}".format(upper=upper, unit_1=unit[1])
        else:
            return "{upper}{unit_1}{time_val}{unit_0}".format(
                upper=upper, time_val=time_val, unit_0=unit[0], unit_1=unit[1]
            )
    else:
        return "{time_val}{unit_0}".format(time_val=time_val, unit_0=unit[0])


def call_shutter_api(config, state):
    if os.environ["DUMMY_MODE"] == "true":
        return True

    result = True
    for shutter in config["shutter"]:
        logging.debug("Request {url}".format(url=shutter["endpoint"][state]))
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


def set_shutter_state(config, state, mode, sense_data=None, host=""):
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

    diff_sec = time.time()
    if exec_hist.exists():
        diff_sec -= exec_hist.stat().st_mtime

    # NOTE: 制御間隔が短く，実際には御できなかった場合，ログを残す．
    if mode == CONTROL_MODE.MANUAL:
        if (diff_sec / 60) < EXEC_INTERVAL_MANUAL_MINUTES:
            app_log(
                (
                    "🔔 シャッターを{state}るのを見合わせました。" + "{time_diff_str}前に{state}ています。{by}"
                ).format(
                    state="開け" if state == "open" else "閉め",
                    time_diff_str=time_str(diff_sec),
                    by="(by {})".format(host) if host != "" else "",
                )
            )
            return get_shutter_state()

    elif mode == CONTROL_MODE.SCHEDULE:
        if (diff_sec / (60 * 60)) < EXEC_INTERVAL_SCHEDULE_HOUR:
            app_log(
                (
                    "🔔 スケジュールに従ってシャッターを{state}るのを見合わせました。"
                    + "{time_diff_str}前に{state}ています。{by}"
                ).format(
                    state="開け" if state == "open" else "閉め",
                    time_diff_str=time_str(diff_sec),
                    by="(by {})".format(host) if host != "" else "",
                )
            )
            return get_shutter_state()
    elif mode == CONTROL_MODE.AUTO:
        if (diff_sec / (60 * 60)) < EXEC_INTERVAL_SCHEDULE_HOUR:
            app_log(
                (
                    "🔔 自動でシャッターを{state}るのを見合わせました。"
                    + "{time_diff_str}前に{state}ています。{by}"
                ).format(
                    state="開け" if state == "open" else "閉め",
                    time_diff_str=time_str(diff_sec),
                    by="(by {})".format(host) if host != "" else "",
                )
            )
            return get_shutter_state()

    result = call_shutter_api(config, state)

    exec_hist.touch()
    exec_inv_hist = STAT_EXEC["close" if state == "open" else "open"]
    exec_inv_hist.unlink(missing_ok=True)

    if result:
        app_log(
            "シャッターを{mode}で{state}ました。{sensor_text}{by}".format(
                mode=mode.value,
                state="開け" if state == "open" else "閉め",
                sensor_text=sensor_text(sense_data),
                by="\n(by {})".format(host) if host != "" else "",
            )
        )
    else:
        app_log(
            "シャッターを{mode}で{state}るのに失敗しました。{sensor_text}{by}".format(
                mode=mode.value,
                state="開け" if state == "open" else "閉め",
                sensor_text=sensor_text(sense_data),
                by="\n(by {})".format(host) if host != "" else "",
            ),
            APP_LOG_LEVEL.ERROR,
        )

    return get_shutter_state()


def sensor_text(sense_data):
    if sense_data is None:
        return ""
    else:
        return "(日射: {solar_rad:.1f} W/m^2, 照度: {lux:.1f} LUX)".format(
            solar_rad=sense_data["solar_rad"]["value"], lux=sense_data["lux"]["value"]
        )


@blueprint.route("/api/shutter_ctrl", methods=["GET", "POST"])
@support_jsonp
@cross_origin()
def api_shutter_ctrl():
    cmd = request.args.get("cmd", 0, type=int)
    state = request.args.get("state", "close", type=str)
    config = current_app.config["CONFIG"]

    if cmd == 1:
        return jsonify(
            dict(
                {"cmd": "set"},
                **set_shutter_state(
                    config, state, CONTROL_MODE.MANUAL, host=remote_host(request)
                )
            )
        )
    else:
        return jsonify(dict({"cmd": "get"}, **get_shutter_state()))


@blueprint.route("/api/dummy/open", methods=["GET"])
@support_jsonp
@cross_origin()
def api_dummy_open():
    logging.info("ダミーのシャッターが開きました．")
    return jsonify({"status": "OK"})


@blueprint.route("/api/dummy/close", methods=["GET"])
@support_jsonp
@cross_origin()
def api_dummy_close():
    logging.info("ダミーのシャッターが閉じました．")
    return jsonify({"status": "OK"})
