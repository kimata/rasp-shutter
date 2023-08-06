# -*- coding: utf-8 -*-
# #!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import os
import pathlib
import threading
from enum import Enum, IntEnum

import requests
from app_scheduler import exec_check_elapsed_time, exec_check_update
from flask_util import auth_user, support_jsonp
from webapp_config import APP_URL_PREFIX, STAT_AUTO_CLOSE, STAT_EXEC_TMPL, STAT_PENDING_OPEN
from webapp_log import APP_LOG_LEVEL, app_log

from flask import Blueprint, current_app, jsonify, request

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

control_lock = threading.Lock()
cmd_hist = []


def init():
    global cmd_hist
    STAT_EXEC_TMPL["open"].parent.mkdir(parents=True, exist_ok=True)
    STAT_EXEC_TMPL["close"].parent.mkdir(parents=True, exist_ok=True)
    cmd_hist = []


def time_str(time_val):
    if time_val >= (60 * 60):
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


def call_shutter_api(config, index, state):
    cmd_hist_push(
        {
            "index": index,
            "state": state,
        }
    )

    if os.environ.get("DUMMY_MODE", "false") == "true":
        return True

    result = True
    shutter = config["shutter"][index]

    logging.debug("Request {url}".format(url=shutter["endpoint"][state]))
    if requests.get(shutter["endpoint"][state]).status_code != 200:
        result = False

    return result


def exec_stat_file(state, index):
    return pathlib.Path(str(STAT_EXEC_TMPL[state]).format(index=index))


def clean_stat_exec(config):
    for index in range(len(config["shutter"])):
        exec_stat_file("open", index).unlink(missing_ok=True)
        exec_stat_file("close", index).unlink(missing_ok=True)


def get_shutter_state(config):
    state_list = []
    for index, shutter in enumerate(config["shutter"]):
        shutter_state = {
            "name": shutter["name"],
        }

        exec_stat_open = exec_stat_file("open", index)
        exec_stat_close = exec_stat_file("close", index)

        if exec_stat_open.exists():
            if exec_stat_close.exists():
                if exec_stat_open.stat().st_mtime > exec_stat_close.stat().st_mtime:
                    shutter_state["state"] = SHUTTER_STATE.OPEN
                else:
                    shutter_state["state"] = SHUTTER_STATE.CLOSE
            else:
                shutter_state["state"] = SHUTTER_STATE.OPEN
        else:
            if exec_stat_close.exists():
                shutter_state["state"] = SHUTTER_STATE.CLOSE
            else:
                shutter_state["state"] = SHUTTER_STATE.UNKNOWN
        state_list.append(shutter_state)

    return {
        "state": state_list,
        "result": "success",
    }


def set_shutter_state_impl(config, index, state, mode, sense_data=None, user=""):
    # NOTE: 閉じている場合に再度閉じるボタンをおしたり，逆に開いている場合に再度
    # 開くボタンを押すことが続くと，スイッチがエラーになるので exec_hist を使って
    # 防止する．exec_hist はこれ以外の目的で使わない．
    exec_hist = exec_stat_file(state, index)
    diff_sec = exec_check_elapsed_time(exec_hist)

    # NOTE: 制御間隔が短く，実際には御できなかった場合，ログを残す．
    if mode == CONTROL_MODE.MANUAL:
        if (diff_sec / 60) < EXEC_INTERVAL_MANUAL_MINUTES:
            app_log(
                ("🔔 {name}のシャッターを{state}るのを見合わせました。" + "{time_diff_str}前に{state}ています。{by}").format(
                    name=config["shutter"][index]["name"],
                    state="開け" if state == "open" else "閉め",
                    time_diff_str=time_str(diff_sec),
                    by="(by {})".format(user) if user != "" else "",
                )
            )
            return get_shutter_state(config)

    elif mode == CONTROL_MODE.SCHEDULE:
        if (diff_sec / (60 * 60)) < EXEC_INTERVAL_SCHEDULE_HOUR:
            app_log(
                ("🔔 スケジュールに従って{name}のシャッターを{state}るのを見合わせました。" + "{time_diff_str}前に{state}ています。{by}").format(
                    name=config["shutter"][index]["name"],
                    state="開け" if state == "open" else "閉め",
                    time_diff_str=time_str(diff_sec),
                    by="(by {})".format(user) if user != "" else "",
                )
            )
            return get_shutter_state(config)
    elif mode == CONTROL_MODE.AUTO:
        if (diff_sec / (60 * 60)) < EXEC_INTERVAL_SCHEDULE_HOUR:  # pragma: no cover
            # NOTE: shutter_auto_close の段階で撥ねられているので，ここには来ない．
            app_log(
                ("🔔 自動で{name}のシャッターを{state}るのを見合わせました。" + "{time_diff_str}前に{state}ています。{by}").format(
                    name=config["shutter"][index]["name"],
                    state="開け" if state == "open" else "閉め",
                    time_diff_str=time_str(diff_sec),
                    by="(by {})".format(user) if user != "" else "",
                )
            )
            return get_shutter_state(config)
    else:  # pragma: no cover
        pass

    result = call_shutter_api(config, index, state)

    exec_check_update(exec_hist)
    exec_inv_hist = exec_stat_file("close" if state == "open" else "open", index)
    exec_inv_hist.unlink(missing_ok=True)

    if result:
        app_log(
            "{name}のシャッターを{mode}で{state}ました。{sensor_text}{by}".format(
                name=config["shutter"][index]["name"],
                mode=mode.value,
                state="開け" if state == "open" else "閉め",
                sensor_text=sensor_text(sense_data),
                by="\n(by {})".format(user) if user != "" else "",
            )
        )
    else:
        app_log(
            "{name}のシャッターを{mode}で{state}るのに失敗しました。{sensor_text}{by}".format(
                name=config["shutter"][index]["name"],
                mode=mode.value,
                state="開け" if state == "open" else "閉め",
                sensor_text=sensor_text(sense_data),
                by="\n(by {})".format(user) if user != "" else "",
            ),
            APP_LOG_LEVEL.ERROR,
        )


def set_shutter_state(config, index_list, state, mode, sense_data=None, user=""):
    if state == "open":
        if mode != CONTROL_MODE.MANUAL:
            # NOTE: 手動以外でシャッターを開けた場合は，
            # 自動で閉じた履歴を削除する．
            STAT_AUTO_CLOSE.unlink(missing_ok=True)
    else:
        # NOTE: シャッターを閉じる指示がされた場合は，
        # 暗くて延期されていた開ける制御を取り消す．
        STAT_PENDING_OPEN.unlink(missing_ok=True)

    with control_lock:
        for index in index_list:
            set_shutter_state_impl(config, index, state, mode)

    return get_shutter_state(config)


def sensor_text(sense_data):
    if sense_data is None:
        return ""
    else:
        return "(日射: {solar_rad:.1f} W/m^2, 照度: {lux:.1f} LUX)".format(
            solar_rad=sense_data["solar_rad"]["value"], lux=sense_data["lux"]["value"]
        )


# NOTE: テスト用のコード
def cmd_hist_push(cmd):  # pragma: no cover
    global cmd_hist

    cmd_hist.append(cmd)
    if len(cmd_hist) > 20:
        cmd_hist.pop(0)


@blueprint.route("/api/shutter_ctrl", methods=["GET", "POST"])
@support_jsonp
def api_shutter_ctrl():
    cmd = request.args.get("cmd", 0, type=int)
    index = request.args.get("index", -1, type=int)
    state = request.args.get("state", "close", type=str)
    config = current_app.config["CONFIG"]

    # NOTE: シャッターが指定されていない場合は，全てを制御対象にする
    if index == -1:
        index_list = list(range(len(config["shutter"])))
    else:
        index_list = [index]

    if cmd == 1:
        return jsonify(
            dict(
                {"cmd": "set"},
                **set_shutter_state(
                    config,
                    index_list,
                    state,
                    CONTROL_MODE.MANUAL,
                    user=auth_user(request),
                ),
            )
        )
    else:
        return jsonify(dict({"cmd": "get"}, **get_shutter_state(config)))


# NOTE: テスト用
@blueprint.route("/api/ctrl/log", methods=["GET"])
@support_jsonp
def api_shutter_ctrl_log():
    global cmd_hist

    cmd = request.args.get("cmd", "get")
    if cmd == "clear":
        cmd_hist = []
        return jsonify(
            {
                "result": "success",
            }
        )
    else:
        return jsonify({"result": "success", "log": cmd_hist})


@blueprint.route("/api/shutter_list", methods=["GET"])
@support_jsonp
def api_shutter_list():
    config = current_app.config["CONFIG"]

    return jsonify(list(map(lambda shutter: shutter["name"], config["shutter"])))


@blueprint.route("/api/dummy/open", methods=["GET"])
@support_jsonp
def api_dummy_open():
    logging.info("ダミーのシャッターが開きました．")
    return jsonify({"status": "OK"})


@blueprint.route("/api/dummy/close", methods=["GET"])
@support_jsonp
def api_dummy_close():
    logging.info("ダミーのシャッターが閉じました．")
    return jsonify({"status": "OK"})
