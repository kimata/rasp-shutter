#!/usr/bin/env python3
import dataclasses
import enum
import logging
import pathlib
import threading
import typing

import flask
import flask_cors
import my_lib.flask_util
import my_lib.footprint
import my_lib.pytest_util
import my_lib.webapp.log
import requests
from flask_pydantic import validate

import rasp_shutter.config
import rasp_shutter.control.config
import rasp_shutter.control.webapi.sensor
import rasp_shutter.metrics.collector
import rasp_shutter.type_defs
import rasp_shutter.util
from rasp_shutter.schemas import CtrlLogRequest, ShutterCtrlRequest


class SHUTTER_STATE(enum.IntEnum):
    OPEN = 0
    CLOSE = 1
    UNKNOWN = 2


class CONTROL_MODE(enum.Enum):
    MANUAL = "🔧手動"
    SCHEDULE = "⏰スケジューラ"
    AUTO = "🤖自動"


MODE_TO_STR: dict[CONTROL_MODE, str] = {
    CONTROL_MODE.MANUAL: "manual",
    CONTROL_MODE.SCHEDULE: "schedule",
    CONTROL_MODE.AUTO: "auto",
}


class ModeIntervalConfig(typing.NamedTuple):
    """モード別の制御間隔設定"""

    divisor: float  # diff_secを割る値（60=分単位、3600=時間単位）
    interval_threshold: float  # この値より短い場合は制御をスキップ
    log_prefix: str  # ログメッセージのプレフィックス


_cfg = rasp_shutter.control.config
MODE_INTERVAL_CONFIG: dict[CONTROL_MODE, ModeIntervalConfig] = {
    CONTROL_MODE.MANUAL: ModeIntervalConfig(60, _cfg.EXEC_INTERVAL_MANUAL_MINUTES, ""),
    CONTROL_MODE.SCHEDULE: ModeIntervalConfig(3600, _cfg.EXEC_INTERVAL_SCHEDULE_HOUR, "スケジュールに従って"),
    CONTROL_MODE.AUTO: ModeIntervalConfig(3600, _cfg.EXEC_INTERVAL_SCHEDULE_HOUR, "自動で"),
}


blueprint = flask.Blueprint("rasp-shutter-control", __name__)

control_lock = threading.Lock()

# ワーカー固有の制御履歴（pytest-xdist並列実行対応）
_cmd_hist: dict[str, list[dict]] = {}


def _get_cmd_hist() -> list[dict]:
    """ワーカー固有の制御履歴リストを取得"""
    worker_id = my_lib.pytest_util.get_worker_id()
    if worker_id not in _cmd_hist:
        _cmd_hist[worker_id] = []
    return _cmd_hist[worker_id]


def _clear_cmd_hist() -> None:
    """ワーカー固有の制御履歴をクリア"""
    worker_id = my_lib.pytest_util.get_worker_id()
    _cmd_hist[worker_id] = []


def init() -> None:
    _clear_cmd_hist()


# 公開API: 制御履歴の取得・クリア用
class _CmdHistWrapper:
    """ワーカー固有の制御履歴へのアクセスを提供するラッパークラス"""

    def __iter__(self):
        return iter(_get_cmd_hist())

    def __len__(self) -> int:
        return len(_get_cmd_hist())

    def __getitem__(self, key: int) -> dict:
        return _get_cmd_hist()[key]

    def append(self, item: dict) -> None:
        _get_cmd_hist().append(item)

    def clear(self) -> None:
        _clear_cmd_hist()

    def copy(self) -> list[dict]:
        return _get_cmd_hist().copy()


cmd_hist = _CmdHistWrapper()


def time_str(time_val: float) -> str:
    """秒数を人間が読みやすい形式に変換"""
    if time_val >= 3600:
        hours, remainder = divmod(int(time_val), 3600)
        minutes = remainder // 60
        if minutes > 0:
            return f"{hours}時間{minutes}分"
        return f"{hours}時間"
    elif time_val >= 60:
        minutes, seconds = divmod(int(time_val), 60)
        if seconds > 0:
            return f"{minutes}分{seconds}秒"
        return f"{minutes}分"
    return f"{int(time_val)}秒"


def call_shutter_api(config: rasp_shutter.config.AppConfig, index: int, state: str) -> bool:
    cmd_hist_push(
        {
            "index": index,
            "state": state,
        }
    )

    if rasp_shutter.util.is_dummy_mode():
        return True

    result = True
    shutter = config.shutter[index]

    endpoint = shutter.endpoint.open if state == "open" else shutter.endpoint.close
    logging.debug("Request %s", endpoint)
    if requests.get(endpoint, timeout=5).status_code != 200:
        result = False

    return result


def exec_stat_file(state: str, index: int) -> pathlib.Path:
    return rasp_shutter.control.config.get_exec_stat_path(state, index)


def clean_stat_exec(config: rasp_shutter.config.AppConfig) -> None:
    for index in range(len(config.shutter)):
        my_lib.footprint.clear(exec_stat_file("open", index))
        my_lib.footprint.clear(exec_stat_file("close", index))

    my_lib.footprint.clear(rasp_shutter.control.config.STAT_PENDING_OPEN.to_path())
    my_lib.footprint.clear(rasp_shutter.control.config.STAT_AUTO_CLOSE.to_path())


def get_shutter_state(config: rasp_shutter.config.AppConfig) -> rasp_shutter.type_defs.ShutterStateResponse:
    state_list: list[rasp_shutter.type_defs.ShutterStateEntry] = []
    for index, shutter in enumerate(config.shutter):
        exec_stat_open = exec_stat_file("open", index)
        exec_stat_close = exec_stat_file("close", index)

        if my_lib.footprint.exists(exec_stat_open):
            if my_lib.footprint.exists(exec_stat_close):
                if my_lib.footprint.compare(exec_stat_open, exec_stat_close):
                    state = SHUTTER_STATE.OPEN
                else:
                    state = SHUTTER_STATE.CLOSE
            else:
                state = SHUTTER_STATE.OPEN
        else:
            if my_lib.footprint.exists(exec_stat_close):  # noqa: SIM108
                state = SHUTTER_STATE.CLOSE
            else:
                state = SHUTTER_STATE.UNKNOWN

        state_list.append(rasp_shutter.type_defs.ShutterStateEntry(name=shutter.name, state=state))

    return rasp_shutter.type_defs.ShutterStateResponse(state=state_list, result="success")


def set_shutter_state_impl(
    config: rasp_shutter.config.AppConfig,
    index: int,
    state: str,
    mode: CONTROL_MODE,
    sense_data: rasp_shutter.type_defs.SensorData | None,
    user: str,
) -> None:
    # NOTE: 閉じている場合に再度閉じるボタンをおしたり、逆に開いている場合に再度
    # 開くボタンを押すことが続くと、スイッチがエラーになるので exec_hist を使って
    # 防止する。また、明るさに基づく自動の開閉が連続するのを防止する。
    # exec_hist はこれ以外の目的で使わない。
    exec_hist = exec_stat_file(state, index)
    diff_sec = my_lib.footprint.elapsed(exec_hist)

    shutter_name = config.shutter[index].name

    # NOTE: 制御間隔が短く、実際には制御できなかった場合、ログを残す。
    state_text = rasp_shutter.type_defs.state_to_action_text(state)
    time_diff_str = time_str(diff_sec)
    by_text = f"(by {user})" if user != "" else ""

    # NamedTupleで制御間隔チェック
    interval_config = MODE_INTERVAL_CONFIG[mode]
    if (diff_sec / interval_config.divisor) < interval_config.interval_threshold:
        my_lib.webapp.log.info(
            f"🔔 {interval_config.log_prefix}{shutter_name}のシャッターを{state_text}るのを見合わせました。"
            f"{time_diff_str}前に{state_text}ています。{by_text}"
        )
        return

    result = call_shutter_api(config, index, state)

    my_lib.footprint.update(exec_hist)
    exec_inv_hist = exec_stat_file("close" if state == "open" else "open", index)
    my_lib.footprint.clear(exec_inv_hist)

    sensor_text_str = sensor_text(sense_data)
    by_newline_text = f"\n(by {user})" if user != "" else ""

    if result:
        my_lib.webapp.log.info(
            f"{shutter_name}のシャッターを{mode.value}で{state_text}ました。{sensor_text_str}{by_newline_text}"
        )

        # メトリクス収集
        try:
            mode_str = MODE_TO_STR[mode]
            metrics_data_path = config.metrics.data
            rasp_shutter.metrics.collector.record_shutter_operation(
                state, mode_str, metrics_data_path, sense_data
            )
        except Exception as e:
            logging.warning("メトリクス記録に失敗しました: %s", e)
    else:
        my_lib.webapp.log.error(
            f"{shutter_name}のシャッターを{mode.value}で{state_text}るのに失敗しました。"
            f"{sensor_text_str}{by_newline_text}"
        )

        # 失敗メトリクス収集
        try:
            metrics_data_path = config.metrics.data
            rasp_shutter.metrics.collector.record_failure(metrics_data_path)
        except Exception as e:
            logging.warning("失敗メトリクス記録に失敗しました: %s", e)


def set_shutter_state(
    config: rasp_shutter.config.AppConfig,
    index_list: list[int],
    state: str,
    mode: CONTROL_MODE,
    sense_data: rasp_shutter.type_defs.SensorData | None,
    user: str = "",
) -> rasp_shutter.type_defs.ShutterStateResponse:
    logging.debug(
        "set_shutter_state index=[%s], state=%s, mode=%s", ",".join(str(n) for n in index_list), state, mode
    )

    if state == "open":
        if mode != CONTROL_MODE.MANUAL:
            # NOTE: 手動以外でシャッターを開けた場合は、
            # 自動で閉じた履歴を削除する。
            my_lib.footprint.clear(rasp_shutter.control.config.STAT_AUTO_CLOSE.to_path())
    else:
        # NOTE: シャッターを閉じる指示がされた場合は、
        # 暗くて延期されていた開ける制御を取り消す。
        my_lib.footprint.clear(rasp_shutter.control.config.STAT_PENDING_OPEN.to_path())

    with control_lock:
        for index in index_list:
            try:
                set_shutter_state_impl(config, index, state, mode, sense_data, user)
            except Exception:
                logging.exception("Failed to control shutter (index=%d)", index)
                continue

    return get_shutter_state(config)


def sensor_text(sense_data: rasp_shutter.type_defs.SensorData | None) -> str:
    if sense_data is None:
        return ""
    else:
        solar_rad = sense_data.solar_rad.value
        lux = sense_data.lux.value
        altitude = sense_data.altitude.value
        return f"(日射: {solar_rad:.1f} W/m^2, 照度: {lux:.1f} LUX, 高度: {altitude:.1f})"


# NOTE: テスト用のコード
def cmd_hist_push(cmd: dict) -> None:  # pragma: no cover
    hist = _get_cmd_hist()
    hist.append(cmd)
    if len(hist) > 20:
        hist.pop(0)


@blueprint.route("/api/shutter_ctrl", methods=["GET", "POST"])
@flask_cors.cross_origin()
@validate(query=ShutterCtrlRequest)
def api_shutter_ctrl(query: ShutterCtrlRequest) -> flask.Response:
    config: rasp_shutter.config.AppConfig = flask.current_app.config["CONFIG"]

    # NOTE: シャッターが指定されていない場合は、全てを制御対象にする
    index_list = list(range(len(config.shutter))) if query.index == -1 else [query.index]

    sense_data = rasp_shutter.control.webapi.sensor.get_sensor_data(config)

    if query.cmd == 1:
        result = set_shutter_state(
            config,
            index_list,
            query.state,
            CONTROL_MODE.MANUAL,
            sense_data,
            my_lib.flask_util.auth_user(flask.request),
        )
        return flask.jsonify(dict({"cmd": "set"}, **dataclasses.asdict(result)))
    else:
        return flask.jsonify(dict({"cmd": "get"}, **dataclasses.asdict(get_shutter_state(config))))


# NOTE: テスト用
@blueprint.route("/api/ctrl/log", methods=["GET"])
@flask_cors.cross_origin()
@validate(query=CtrlLogRequest)
def api_shutter_ctrl_log(query: CtrlLogRequest) -> flask.Response:
    if query.cmd == "clear":
        _clear_cmd_hist()
        return flask.jsonify(
            {
                "result": "success",
            }
        )
    else:
        return flask.jsonify({"result": "success", "log": _get_cmd_hist()})


@blueprint.route("/api/shutter_list", methods=["GET"])
@flask_cors.cross_origin()
def api_shutter_list() -> flask.Response:
    config: rasp_shutter.config.AppConfig = flask.current_app.config["CONFIG"]

    return flask.jsonify([shutter.name for shutter in config.shutter])


if rasp_shutter.util.is_dummy_mode():

    @blueprint.route("/api/dummy/open", methods=["GET"])
    @my_lib.flask_util.support_jsonp
    def api_dummy_open() -> flask.Response:
        logging.info("ダミーのシャッターが開きました。")
        return flask.jsonify({"status": "OK"})

    @blueprint.route("/api/dummy/close", methods=["GET"])
    @my_lib.flask_util.support_jsonp
    def api_dummy_close() -> flask.Response:
        logging.info("ダミーのシャッターが閉じました。")
        return flask.jsonify({"status": "OK"})

    @blueprint.route("/api/ctrl/clear", methods=["POST"])
    @my_lib.flask_util.support_jsonp
    def api_test_control_clear() -> flask.Response:
        """テスト用: 制御履歴をクリア"""
        config: rasp_shutter.config.AppConfig = flask.current_app.config["CONFIG"]
        clean_stat_exec(config)
        return flask.jsonify({"status": "OK"})
