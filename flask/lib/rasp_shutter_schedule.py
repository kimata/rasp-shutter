#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import threading
import urllib.parse
from multiprocessing import Queue

import app_scheduler
from flask_cors import cross_origin
from flask_util import auth_user, support_jsonp
from webapp_config import APP_URL_PREFIX
from webapp_event import EVENT_TYPE, notify_event
from webapp_log import APP_LOG_LEVEL, app_log

from flask import Blueprint, jsonify, request, url_for

WDAY_STR = ["日", "月", "火", "水", "木", "金", "土"]


blueprint = Blueprint("rasp-shutter-schedule", __name__, url_prefix=APP_URL_PREFIX)

schedule_lock = threading.Lock()
schedule_queue = None
worker = None


def init(config):
    global worker
    global schedule_queue

    assert worker is None

    schedule_queue = Queue()
    app_scheduler.init()
    worker = threading.Thread(
        target=app_scheduler.schedule_worker,
        args=(
            config,
            schedule_queue,
        ),
    )
    worker.start()


def term():
    global worker

    if worker is None:
        return

    app_scheduler.should_terminate = True
    worker.join()
    worker = None


def wday_str_list(wday_list, lang="en"):
    wday_str = WDAY_STR
    return map(lambda i: wday_str[i], (i for i in range(len(wday_list)) if wday_list[i]))


def schedule_entry_str(name, entry):
    return "{name} {time} {solar_rad} W/mm^2 {lux} LUX {wday}".format(
        name=name.upper(),
        time=entry["time"],
        solar_rad=entry["solar_rad"],
        lux=entry["lux"],
        wday=",".join(wday_str_list(entry["wday"], "ja")),
    )


def schedule_str(schedule_data):
    str = []
    for name in ["open", "close"]:
        entry = schedule_data[name]
        if not entry["is_active"]:
            continue
        str.append(schedule_entry_str(name, entry))

    if len(str) == 0:
        return "∅ 全て無効"

    return "、\n".join(str)


@blueprint.route("/api/schedule_ctrl", methods=["GET", "POST"])
@support_jsonp
@cross_origin()
def api_schedule_ctrl():
    cmd = request.args.get("cmd", None)
    data = request.args.get("data", None)
    if cmd == "set":
        schedule_data = json.loads(data)

        if not app_scheduler.schedule_validate(schedule_data):
            app_log(
                "😵 スケジュールの指定が不正です。",
                APP_LOG_LEVEL.ERROR,
            )
            return jsonify(app_scheduler.schedule_load())

        with schedule_lock:
            schedule_data = json.loads(data)

            endpoint = urllib.parse.urljoin(
                request.url_root,
                url_for("rasp-shutter-control.api_shutter_ctrl"),
            )

            for name, entry in schedule_data.items():
                entry["endpoint"] = endpoint
            schedule_queue.put(schedule_data)

            # NOTE: 本来は schedule_worker の中だけで呼んでるので不要だけど，
            # レスポンスを schedule_load() で返したいので，ここでも呼ぶ．
            app_scheduler.schedule_store(schedule_data)

            notify_event(EVENT_TYPE.SCHEDULE)

            user = auth_user(request)
            app_log(
                "📅 スケジュールを更新しました。\n{schedule}\n{by}".format(
                    schedule=schedule_str(schedule_data),
                    by="by {}".format(user) if user != "" else "",
                )
            )

    return jsonify(app_scheduler.schedule_load())
