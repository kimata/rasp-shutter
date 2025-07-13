#!/usr/bin/env python3
import enum
import logging
import os
import pathlib
import threading

import my_lib.flask_util
import my_lib.footprint
import my_lib.webapp.config
import my_lib.webapp.log
import rasp_shutter.control.config
import rasp_shutter.metrics.collector
import requests

import flask

# この時間内に同じ制御がスケジューラで再度リクエストされた場合、
# 実行をやめる。
EXEC_INTERVAL_SCHEDULE_HOUR = 12
# この時間内に同じ制御が手動で再度リクエストされた場合、
# 実行をやめる。
EXEC_INTERVAL_MANUAL_MINUTES = 1


class SHUTTER_STATE(enum.IntEnum):  # noqa: N801
    OPEN = 0
    CLOSE = 1
    UNKNOWN = 2


class CONTROL_MODE(enum.Enum):  # noqa: N801
    MANUAL = "🔧手動"
    SCHEDULE = "⏰スケジューラ"
    AUTO = "🤖自動"


blueprint = flask.Blueprint("rasp-shutter-control", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)

control_lock = threading.Lock()
cmd_hist = []


def init():
    global cmd_hist  # noqa: PLW0603
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
            return f"{upper}{unit[1]}"
        else:
            return f"{upper}{unit[1]}{time_val}{unit[0]}"
    else:
        return f"{time_val}{unit[0]}"


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

    logging.debug("Request %s", shutter["endpoint"][state])
    if requests.get(shutter["endpoint"][state], timeout=5).status_code != 200:
        result = False

    return result


def exec_stat_file(state, index):
    return pathlib.Path(str(rasp_shutter.control.config.STAT_EXEC_TMPL[state]).format(index=index))


def clean_stat_exec(config):
    for index in range(len(config["shutter"])):
        my_lib.footprint.clear(exec_stat_file("open", index))
        my_lib.footprint.clear(exec_stat_file("close", index))


def get_shutter_state(config):
    state_list = []
    for index, shutter in enumerate(config["shutter"]):
        shutter_state = {
            "name": shutter["name"],
        }

        exec_stat_open = exec_stat_file("open", index)
        exec_stat_close = exec_stat_file("close", index)

        if my_lib.footprint.exists(exec_stat_open):
            if my_lib.footprint.exists(exec_stat_close):
                if my_lib.footprint.compare(exec_stat_open, exec_stat_close):
                    shutter_state["state"] = SHUTTER_STATE.OPEN
                else:
                    shutter_state["state"] = SHUTTER_STATE.CLOSE
            else:
                shutter_state["state"] = SHUTTER_STATE.OPEN
        else:  # noqa: PLR5501
            if my_lib.footprint.exists(exec_stat_close):
                shutter_state["state"] = SHUTTER_STATE.CLOSE
            else:
                shutter_state["state"] = SHUTTER_STATE.UNKNOWN
        state_list.append(shutter_state)

    return {
        "state": state_list,
        "result": "success",
    }


def set_shutter_state_impl(config, index, state, mode, sense_data, user):  # noqa: PLR0913
    # NOTE: 閉じている場合に再度閉じるボタンをおしたり、逆に開いている場合に再度
    # 開くボタンを押すことが続くと、スイッチがエラーになるので exec_hist を使って
    # 防止する。また、明るさに基づく自動の開閉が連続するのを防止する。
    # exec_hist はこれ以外の目的で使わない。
    exec_hist = exec_stat_file(state, index)
    diff_sec = my_lib.footprint.elapsed(exec_hist)

    # NOTE: 制御間隔が短く、実際には御できなかった場合、ログを残す。
    if mode == CONTROL_MODE.MANUAL:
        if (diff_sec / 60) < EXEC_INTERVAL_MANUAL_MINUTES:
            my_lib.webapp.log.info(
                (
                    "🔔 {name}のシャッターを{state}るのを見合わせました。"
                    "{time_diff_str}前に{state}ています。{by}"
                ).format(
                    name=config["shutter"][index]["name"],
                    state="開け" if state == "open" else "閉め",
                    time_diff_str=time_str(diff_sec),
                    by=f"(by {user})" if user != "" else "",
                )
            )
            return

    elif mode == CONTROL_MODE.SCHEDULE:
        if (diff_sec / (60 * 60)) < EXEC_INTERVAL_SCHEDULE_HOUR:
            my_lib.webapp.log.info(
                (
                    "🔔 スケジュールに従って{name}のシャッターを{state}るのを見合わせました。"
                    "{time_diff_str}前に{state}ています。{by}"
                ).format(
                    name=config["shutter"][index]["name"],
                    state="開け" if state == "open" else "閉め",
                    time_diff_str=time_str(diff_sec),
                    by=f"(by {user})" if user != "" else "",
                )
            )
            return
    elif mode == CONTROL_MODE.AUTO:
        if (diff_sec / (60 * 60)) < EXEC_INTERVAL_SCHEDULE_HOUR:
            my_lib.webapp.log.info(
                (
                    "🔔 自動で{name}のシャッターを{state}るのを見合わせました。"
                    "{time_diff_str}前に{state}ています。{by}"
                ).format(
                    name=config["shutter"][index]["name"],
                    state="開け" if state == "open" else "閉め",
                    time_diff_str=time_str(diff_sec),
                    by=f"(by {user})" if user != "" else "",
                )
            )
            return
    else:  # pragma: no cover
        pass

    result = call_shutter_api(config, index, state)

    my_lib.footprint.update(exec_hist)
    exec_inv_hist = exec_stat_file("close" if state == "open" else "open", index)
    my_lib.footprint.clear(exec_inv_hist)

    if result:
        my_lib.webapp.log.info(
            "{name}のシャッターを{mode}で{state}ました。{sensor_text}{by}".format(
                name=config["shutter"][index]["name"],
                mode=mode.value,
                state="開け" if state == "open" else "閉め",
                sensor_text=sensor_text(sense_data) if mode != CONTROL_MODE.MANUAL else "",
                by=f"\n(by {user})" if user != "" else "",
            )
        )

        # メトリクス収集
        try:
            mode_str = (
                "manual"
                if mode == CONTROL_MODE.MANUAL
                else "schedule"
                if mode == CONTROL_MODE.SCHEDULE
                else "auto"
            )
            metrics_data_path = config.get("metrics", {}).get("data")
            rasp_shutter.metrics.collector.record_shutter_operation(
                state, mode_str, metrics_data_path, sense_data
            )
        except Exception as e:
            logging.warning("メトリクス記録に失敗しました: %s", e)
    else:
        my_lib.webapp.log.error(
            "{name}のシャッターを{mode}で{state}るのに失敗しました。{sensor_text}{by}".format(
                name=config["shutter"][index]["name"],
                mode=mode.value,
                state="開け" if state == "open" else "閉め",
                sensor_text=sensor_text(sense_data) if mode != CONTROL_MODE.MANUAL else "",
                by=f"\n(by {user})" if user != "" else "",
            )
        )

        # 失敗メトリクス収集
        try:
            metrics_data_path = config.get("metrics", {}).get("data")
            rasp_shutter.metrics.collector.record_failure(metrics_data_path)
        except Exception as e:
            logging.warning("失敗メトリクス記録に失敗しました: %s", e)


def set_shutter_state(config, index_list, state, mode, sense_data, user=""):  # noqa: PLR0913
    logging.debug(
        "set_shutter_state index=(%s), state=%s, mode=%s", ",".join(str(n) for n in index_list), state, mode
    )

    if state == "open":
        if mode != CONTROL_MODE.MANUAL:
            # NOTE: 手動以外でシャッターを開けた場合は、
            # 自動で閉じた履歴を削除する。
            my_lib.footprint.clear(rasp_shutter.control.config.STAT_AUTO_CLOSE)
    else:
        # NOTE: シャッターを閉じる指示がされた場合は、
        # 暗くて延期されていた開ける制御を取り消す。
        my_lib.footprint.clear(rasp_shutter.control.config.STAT_PENDING_OPEN)

    with control_lock:
        for index in index_list:
            try:
                set_shutter_state_impl(config, index, state, mode, sense_data, user)
            except Exception:  # noqa: PERF203
                logging.exception("Failed to control shutter (index=%d)", index)
                continue

    return get_shutter_state(config)


def sensor_text(sense_data):
    if sense_data is None:
        return ""
    else:
        return "(日射: {solar_rad:.1f} W/m^2, 照度: {lux:.1f} LUX, 高度: {altitude:.1f})".format(
            solar_rad=sense_data["solar_rad"]["value"],
            lux=sense_data["lux"]["value"],
            altitude=sense_data["altitude"]["value"],
        )


# NOTE: テスト用のコード
def cmd_hist_push(cmd):  # pragma: no cover
    global cmd_hist

    cmd_hist.append(cmd)
    if len(cmd_hist) > 20:
        cmd_hist.pop(0)


@blueprint.route("/api/shutter_ctrl", methods=["GET", "POST"])
@my_lib.flask_util.support_jsonp
def api_shutter_ctrl():
    cmd = flask.request.args.get("cmd", 0, type=int)
    index = flask.request.args.get("index", -1, type=int)
    state = flask.request.args.get("state", "close", type=str)
    config = flask.current_app.config["CONFIG"]

    # NOTE: シャッターが指定されていない場合は、全てを制御対象にする
    index_list = list(range(len(config["shutter"]))) if index == -1 else [index]

    sense_data = rasp_shutter.control.webapi.sensor.get_sensor_data(config)

    if cmd == 1:
        return flask.jsonify(
            dict(
                {"cmd": "set"},
                **set_shutter_state(
                    config,
                    index_list,
                    state,
                    CONTROL_MODE.MANUAL,
                    sense_data,
                    my_lib.flask_util.auth_user(flask.request),
                ),
            )
        )
    else:
        return flask.jsonify(dict({"cmd": "get"}, **get_shutter_state(config)))


# NOTE: テスト用
@blueprint.route("/api/ctrl/log", methods=["GET"])
@my_lib.flask_util.support_jsonp
def api_shutter_ctrl_log():
    global cmd_hist  # noqa: PLW0603

    cmd = flask.request.args.get("cmd", "get")
    if cmd == "clear":
        cmd_hist = []
        return flask.jsonify(
            {
                "result": "success",
            }
        )
    else:
        return flask.jsonify({"result": "success", "log": cmd_hist})


@blueprint.route("/api/shutter_list", methods=["GET"])
@my_lib.flask_util.support_jsonp
def api_shutter_list():
    config = flask.current_app.config["CONFIG"]

    return flask.jsonify([shutter["name"] for shutter in config["shutter"]])


if os.environ.get("DUMMY_MODE", "false") == "true":

    @blueprint.route("/api/dummy/open", methods=["GET"])
    @my_lib.flask_util.support_jsonp
    def api_dummy_open():
        logging.info("ダミーのシャッターが開きました。")
        return flask.jsonify({"status": "OK"})

    @blueprint.route("/api/dummy/close", methods=["GET"])
    @my_lib.flask_util.support_jsonp
    def api_dummy_close():
        logging.info("ダミーのシャッターが閉じました。")
        return flask.jsonify({"status": "OK"})

    @blueprint.route("/api/ctrl/clear", methods=["POST"])
    @my_lib.flask_util.support_jsonp
    def api_test_control_clear():
        """テスト用: 制御履歴をクリア"""
        config = flask.current_app.config["CONFIG"]
        clean_stat_exec(config)
        return flask.jsonify({"status": "OK"})
