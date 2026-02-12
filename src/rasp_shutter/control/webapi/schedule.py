#!/usr/bin/env python3
import json
import multiprocessing
import threading
import urllib.parse

import flask
import flask_cors
import my_lib.flask_util
import my_lib.pytest_util
import my_lib.webapp.config
import my_lib.webapp.event
import my_lib.webapp.log
from flask_pydantic import validate

import rasp_shutter.control.scheduler
import rasp_shutter.type_defs
from rasp_shutter.schemas import ScheduleCtrlRequest

blueprint = flask.Blueprint("rasp-shutter-schedule", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)

_schedule_lock: dict[str, threading.RLock] = {}
_schedule_queue: dict[str, "multiprocessing.Queue[dict[str, bool]]"] = {}
_worker_thread: dict[str, threading.Thread] = {}

WDAY_STR = ["日", "月", "火", "水", "木", "金", "土"]


def init(config):
    init_impl(config)


def term():
    worker_thread = get_worker_thread()
    if worker_thread is None:
        return

    rasp_shutter.control.scheduler.term()
    worker_thread.join()
    del _worker_thread[my_lib.pytest_util.get_worker_id()]


def init_impl(config):
    if get_worker_thread() is not None:
        raise ValueError("worker should be None")

    worker_id = my_lib.pytest_util.get_worker_id()

    _schedule_queue[worker_id] = multiprocessing.Queue()
    _schedule_lock[worker_id] = threading.RLock()
    rasp_shutter.control.scheduler.init()

    _worker_thread[worker_id] = threading.Thread(
        target=rasp_shutter.control.scheduler.schedule_worker,
        args=(
            config,
            get_schedule_queue(),
        ),
    )
    _worker_thread[worker_id].start()


def get_schedule_lock():
    return _schedule_lock.get(my_lib.pytest_util.get_worker_id(), None)


def get_schedule_queue():
    return _schedule_queue.get(my_lib.pytest_util.get_worker_id(), None)


def get_worker_thread():
    return _worker_thread.get(my_lib.pytest_util.get_worker_id(), None)


def wday_str_list(wday_list: list[bool]) -> list[str]:
    wday_str = WDAY_STR

    return [wday_str[i] for i, is_active in enumerate(wday_list) if is_active]


def schedule_entry_str(name: str, entry: rasp_shutter.type_defs.ScheduleEntry) -> str:
    name_upper = name.upper()
    time = entry["time"]
    solar_rad = entry["solar_rad"]
    lux = entry["lux"]
    altitude = entry["altitude"]
    wday = ",".join(wday_str_list(entry["wday"]))
    return f"{name_upper} {time} {solar_rad} W/mm^2 {lux} LUX {altitude} deg {wday}"


def schedule_str(schedule_data: dict) -> str:
    str_buf = []
    for name in ["open", "close"]:
        entry = schedule_data[name]
        if not entry["is_active"]:
            continue
        str_buf.append(schedule_entry_str(name, entry))

    if len(str_buf) == 0:
        return "∅ 全て無効"

    return "、\n".join(str_buf)


@blueprint.route("/api/schedule_ctrl", methods=["GET", "POST"])
@flask_cors.cross_origin()
@validate(query=ScheduleCtrlRequest)
def api_schedule_ctrl(query: ScheduleCtrlRequest) -> flask.Response:
    if query.cmd == "set" and query.data is not None:
        schedule_data = json.loads(query.data)

        if not rasp_shutter.control.scheduler.schedule_validate(schedule_data):
            my_lib.webapp.log.error("😵 スケジュールの指定が不正です。")
            return flask.jsonify(rasp_shutter.control.scheduler.schedule_load())

        schedule_lock = get_schedule_lock()
        schedule_queue = get_schedule_queue()
        assert schedule_lock is not None  # noqa: S101
        assert schedule_queue is not None  # noqa: S101

        with schedule_lock:
            schedule_data = json.loads(query.data)

            endpoint = urllib.parse.urljoin(
                flask.request.url_root,
                flask.url_for("rasp-shutter-control.api_shutter_ctrl"),
            )

            for entry in schedule_data.values():
                entry["endpoint"] = endpoint
            schedule_queue.put(schedule_data)

            rasp_shutter.control.scheduler.schedule_store(schedule_data)
            my_lib.webapp.event.notify_event(my_lib.webapp.event.EVENT_TYPE.SCHEDULE)

            user = my_lib.flask_util.auth_user(flask.request)
            schedule_text = schedule_str(schedule_data)
            by_text = f"by {user}" if user != "" else ""
            my_lib.webapp.log.info(f"📅 スケジュールを更新しました。\n{schedule_text}\n{by_text}")

    return flask.jsonify(rasp_shutter.control.scheduler.schedule_load())
