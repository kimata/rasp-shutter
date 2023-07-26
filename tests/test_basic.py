#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import pathlib
import pytest
import re
import time
import json
import datetime
from unittest import mock

sys.path.append(str(pathlib.Path(__file__).parent.parent / "flask" / "app"))

from app import create_app

CONFIG_FILE = "config.example.yaml"


@pytest.fixture(scope="session", autouse=True)
def slack_mock():
    with mock.patch(
        "notify_slack.slack_sdk.web.client.WebClient.chat_postMessage",
        retunr_value=True,
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session")
def app(mocker):
    mocker.patch.dict("os.environ", {"TEST": "true"})
    mocker.patch.dict("os.environ", {"WERKZEUG_RUN_MAIN": "true"})

    import webapp_config

    webapp_config.SCHEDULE_DATA_PATH.unlink(missing_ok=True)

    app = create_app(CONFIG_FILE, dummy_mode=True)

    yield app

    # NOTE: 特定のテストのみ実行したときのため，ここでも呼ぶ
    test_terminate()


@pytest.fixture()
def client(app, mocker):
    test_client = app.test_client()

    yield test_client

    test_client.delete()


def time_morning(offset_min=0):
    return datetime.datetime.now().replace(hour=7, minute=0 + offset_min, second=0)


def time_evening(offset_min=0):
    return datetime.datetime.now().replace(hour=17, minute=0 + offset_min, second=0)


def time_str(time):
    return time.strftime("%H:%M")


SENSOR_DATA_DARK = {
    "lux": {"valid": True, "value": 10},
    "solar_rad": {"valid": True, "value": 10},
}
SENSOR_DATA_BRIGHT = {
    "solar_rad": {"valid": True, "value": 200},
    "lux": {"valid": True, "value": 2000},
}


def gen_schedule_data():
    schedule_data = {
        "is_active": True,
        "solar_rad": 0,
        "lux": 0,
        "wday": [True] * 7,
    }

    return {
        "open": schedule_data
        | {"time": time_str(time_morning(1)), "solar_rad": 150, "lux": 1000},
        "close": schedule_data
        | {"time": time_str(time_evening(1)), "solar_rad": 80, "lux": 1200},
    }


def ctrl_log_clear(client):
    response = client.get(
        "/rasp-shutter/api/ctrl/log",
        query_string={
            "cmd": "clear",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"


def ctrl_log_check(client, expect):
    response = client.get("/rasp-shutter/api/ctrl/log")
    assert response.status_code == 200
    assert response.json["result"] == "success"

    assert response.json["log"] == expect


def ctrl_stat_clear():
    import rasp_shutter_control
    from config import load_config
    from webapp_config import STAT_AUTO_CLOSE

    rasp_shutter_control.clean_stat_exec(load_config(CONFIG_FILE))

    STAT_AUTO_CLOSE.unlink(missing_ok=True)


######################################################################
def test_redirect(client):
    ctrl_log_check(client, [])

    response = client.get("/")
    assert response.status_code == 302
    assert re.search(r"/rasp-shutter/$", response.location)

    ctrl_log_check(client, [])


def test_index(client):
    ctrl_log_clear(client)

    response = client.get("/rasp-shutter/")
    assert response.status_code == 200
    assert "電動シャッター" in response.data.decode("utf-8")

    response = client.get("/rasp-shutter/", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200

    ctrl_log_check(client, [])


def test_index_with_other_status(client, mocker):
    mocker.patch(
        "flask.wrappers.Response.status_code",
        return_value=301,
        new_callable=mocker.PropertyMock,
    )

    response = client.get("/rasp-shutter/", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 301


def test_shutter_ctrl_read(client):
    ctrl_log_clear(client)

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(client, [])


def test_shutter_ctrl_inconsistent_read(client):
    import app_scheduler
    import rasp_shutter_control

    ctrl_log_clear(client)

    # NOTE: 本来ないはずの，oepn と close の両方のファイルが存在する場合 (close が後)
    ctrl_stat_clear()
    app_scheduler.exec_check_update(rasp_shutter_control.exec_stat_file("open", 0))
    time.sleep(0.1)
    app_scheduler.exec_check_update(rasp_shutter_control.exec_stat_file("close", 0))

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"
    assert (
        response.json["state"][0]["state"] == rasp_shutter_control.SHUTTER_STATE.CLOSE
    )
    assert (
        response.json["state"][1]["state"] == rasp_shutter_control.SHUTTER_STATE.UNKNOWN
    )

    # NOTE: 本来ないはずの，oepn と close の両方のファイルが存在する場合 (open が後)
    ctrl_stat_clear()
    app_scheduler.exec_check_update(rasp_shutter_control.exec_stat_file("close", 1))
    time.sleep(0.1)
    app_scheduler.exec_check_update(rasp_shutter_control.exec_stat_file("open", 1))

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"
    assert response.json["state"][1]["state"] == rasp_shutter_control.SHUTTER_STATE.OPEN
    assert (
        response.json["state"][0]["state"] == rasp_shutter_control.SHUTTER_STATE.UNKNOWN
    )

    ctrl_log_check(client, [])


def test_valve_ctrl_manual_single_1(client, mocker):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 0,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(client, [{"index": 0, "state": "open"}])

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 0,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client, [{"index": 0, "state": "open"}, {"index": 0, "state": "close"}]
    )


def test_valve_ctrl_manual_single_2(client):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 1,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(client, [{"index": 1, "state": "open"}])

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 1,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client, [{"index": 1, "state": "open"}, {"index": 1, "state": "close"}]
    )


def test_valve_ctrl_manual_all(client):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 0,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(client, [{"index": 0, "state": "open"}])

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 1,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client, [{"index": 0, "state": "open"}, {"index": 1, "state": "open"}]
    )

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 1,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
            {"index": 1, "state": "close"},
        ],
    )

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 0,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
            {"index": 1, "state": "close"},
            {"index": 0, "state": "close"},
        ],
    )

    ctrl_log_clear(client)

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
        ],
    )

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
        ],
    )

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
        ],
    )


def test_valve_ctrl_manual_single_fail(client, mocker):
    import requests
    import notify_slack

    ctrl_log_clear(client)
    ctrl_stat_clear()
    notify_slack.clear_interval()

    # NOTE: このテストだけは，制御の止め方を変える
    def request_mock(url):
        request_mock.i += 1
        response = requests.models.Response()
        if request_mock.i == 1:
            response.status_code = 500
        else:
            response.status_code = 200
        return response

    request_mock.i = 0

    mocker.patch.dict(os.environ, {"DUMMY_MODE": "false"}, clear=True)
    mocker.patch("rasp_shutter_control.requests.get", side_effect=request_mock)

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 1,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 1, "state": "open"},
        ],
    )

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 1,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 1, "state": "open"},
            {"index": 1, "state": "close"},
        ],
    )

    # NOTE: ログを出し切らせる
    time.sleep(2)


def test_event(client):
    ctrl_log_clear(client)

    response = client.get("/rasp-shutter/api/event", query_string={"count": "2"})
    assert response.status_code == 200
    assert response.data.decode()

    ctrl_log_check(client, [])


def test_schedule_ctrl_inactive(client, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    schedule_data = gen_schedule_data()
    schedule_data["open"]["is_active"] = False
    schedule_data["close"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200
    time.sleep(0.6)

    freezer.move_to(time_morning(1))
    time.sleep(0.6)

    freezer.move_to(time_morning(2))
    time.sleep(0.6)

    freezer.move_to(time_morning(3))
    time.sleep(0.6)

    freezer.move_to(time_evening(1))
    time.sleep(0.6)

    freezer.move_to(time_evening(2))
    time.sleep(0.6)

    freezer.move_to(time_evening(3))
    time.sleep(0.6)

    schedule_data["open"]["is_active"] = True
    schedule_data["open"]["wday"] = [False] * 7
    schedule_data["close"]["is_active"] = True
    schedule_data["close"]["wday"] = [False] * 7
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200
    time.sleep(0.6)

    freezer.move_to(time_morning(1))
    time.sleep(0.6)

    freezer.move_to(time_morning(2))
    time.sleep(0.6)

    freezer.move_to(time_morning(3))
    time.sleep(0.6)

    freezer.move_to(time_evening(1))
    time.sleep(0.6)

    freezer.move_to(time_evening(2))
    time.sleep(0.6)

    freezer.move_to(time_evening(3))
    time.sleep(0.6)

    ctrl_log_check(client, [])


def test_schedule_ctrl_invalid(client, mocker):
    import notify_slack

    ctrl_log_clear(client)
    notify_slack.clear_interval()

    schedule_data = gen_schedule_data()
    del schedule_data["open"]
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    schedule_data = gen_schedule_data()
    del schedule_data["open"]["is_active"]
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    schedule_data = gen_schedule_data()
    schedule_data["open"]["is_active"] = "TEST"
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    schedule_data = gen_schedule_data()
    schedule_data["open"]["lux"] = "TEST"
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    schedule_data = gen_schedule_data()
    schedule_data["open"]["solar_rad"] = "TEST"
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    schedule_data = gen_schedule_data()
    schedule_data["open"]["time"] = "TEST"
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    schedule_data = gen_schedule_data()
    schedule_data["open"]["wday"] = [True] * 5
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    schedule_data = gen_schedule_data()
    schedule_data["open"]["wday"] = ["TEST"] * 7
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    ctrl_log_check(client, [])

    # NOTE: ログを出し切らせる
    time.sleep(2)


def test_schedule_ctrl_execute(client, mocker, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    mocker.patch("rasp_shutter_sensor.get_sensor_data", return_value=SENSOR_DATA_BRIGHT)

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    freezer.move_to(time_evening(0))

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 1,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    schedule_data = gen_schedule_data()
    schedule_data["open"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    time.sleep(0.6)

    freezer.move_to(time_evening(1))
    time.sleep(0.6)

    freezer.move_to(time_evening(2))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
            {"index": 1, "state": "close"},
            {"index": 0, "state": "close"},
        ],
    )


def test_schedule_ctrl_auto_close(client, mocker, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    sensor_data_mock = mocker.patch("rasp_shutter_sensor.get_sensor_data")

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

    schedule_data = gen_schedule_data()
    schedule_data["open"]["is_active"] = False
    schedule_data["close"]["time"] = time_str(time_evening(5))
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    freezer.move_to(time_evening(1))
    time.sleep(0.6)

    freezer.move_to(time_evening(2))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
        ],
    )

    sensor_data_mock.return_value = SENSOR_DATA_DARK

    freezer.move_to(time_evening(3))
    time.sleep(1)

    freezer.move_to(time_evening(4))
    time.sleep(1)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
        ],
    )

    freezer.move_to(time_evening(5))
    time.sleep(0.6)

    freezer.move_to(time_evening(6))
    time.sleep(0.6)
    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
        ],
    )


def test_schedule_ctrl_auto_close_dup(client, mocker, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    sensor_data_mock = mocker.patch("rasp_shutter_sensor.get_sensor_data")

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    freezer.move_to(time_evening(0))

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 1,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
            {"index": 1, "state": "close"},
        ],
    )

    sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

    schedule_data = gen_schedule_data()
    schedule_data["close"]["time"] = time_str(time_evening(4))
    schedule_data["open"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    freezer.move_to(time_evening(1))
    time.sleep(0.6)

    freezer.move_to(time_evening(2))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
            {"index": 1, "state": "close"},
        ],
    )

    sensor_data_mock.return_value = SENSOR_DATA_DARK

    freezer.move_to(time_evening(3))
    time.sleep(1)

    freezer.move_to(time_evening(4))
    time.sleep(1)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
            {"index": 1, "state": "close"},
            {"index": 0, "state": "close"},
        ],
    )

    freezer.move_to(time_evening(5))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
            {"index": 1, "state": "close"},
            {"index": 0, "state": "close"},
        ],
    )


def test_schedule_ctrl_auto_inactive(client, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    schedule_data = gen_schedule_data()
    schedule_data["open"]["is_active"] = False
    schedule_data["close"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    freezer.move_to(time_morning(1))
    time.sleep(0.6)

    freezer.move_to(time_morning(2))
    time.sleep(0.6)

    freezer.move_to(time_evening(1))
    time.sleep(0.6)

    freezer.move_to(time_evening(2))
    time.sleep(0.6)

    ctrl_log_check(client, [])


def test_schedule_ctrl_pending_open(client, mocker, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    sensor_data_mock = mocker.patch("rasp_shutter_sensor.get_sensor_data")

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    sensor_data_mock.return_value = SENSOR_DATA_DARK

    schedule_data = gen_schedule_data()
    schedule_data["open"]["time"] = time_str(time_morning(3))
    schedule_data["close"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
        ],
    )

    freezer.move_to(time_morning(1))
    time.sleep(0.6)

    freezer.move_to(time_morning(2))
    time.sleep(0.6)

    freezer.move_to(time_morning(3))
    time.sleep(0.6)

    sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

    freezer.move_to(time_morning(4))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
            {"cmd": "pending", "state": "open"},
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
        ],
    )


def test_schedule_ctrl_pending_open_inactive(client, mocker, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    sensor_data_mock = mocker.patch("rasp_shutter_sensor.get_sensor_data")

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    sensor_data_mock.return_value = SENSOR_DATA_DARK

    schedule_data = gen_schedule_data()
    schedule_data["close"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
        ],
    )

    freezer.move_to(time_morning(1))
    time.sleep(0.6)

    freezer.move_to(time_morning(2))
    time.sleep(0.6)

    freezer.move_to(time_morning(3))
    time.sleep(0.6)

    # NOTE: pending open になった後に，open が inactive
    schedule_data = gen_schedule_data()
    schedule_data["open"]["is_active"] = False
    schedule_data["close"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )

    sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

    freezer.move_to(time_morning(4))
    time.sleep(0.6)

    freezer.move_to(time_morning(5))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
        ],
    )


# NOTE: 開けるのを延期したあとでセンサーエラー
def test_schedule_ctrl_pending_open_fail(client, mocker, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    mocker.patch("slack_sdk.WebClient.chat_postMessage", return_value=True)
    sensor_data_mock = mocker.patch("rasp_shutter_sensor.get_sensor_data")

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
        ],
    )

    sensor_data_mock.return_value = SENSOR_DATA_DARK

    schedule_data = gen_schedule_data()
    schedule_data["close"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    freezer.move_to(time_morning(1))
    time.sleep(0.6)

    sensor_data = SENSOR_DATA_BRIGHT.copy()
    sensor_data["lux"] = {"valid": False, "value": 5000}
    sensor_data_mock.return_value = sensor_data

    freezer.move_to(time_morning(2))
    time.sleep(0.6)

    freezer.move_to(time_morning(3))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
        ],
    )


def test_schedule_ctrl_open_dup(client, mocker, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    mocker.patch("rasp_shutter_sensor.get_sensor_data", return_value=SENSOR_DATA_BRIGHT)

    freezer.move_to(time_morning(0))
    time.sleep(1.6)

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
        ],
    )

    schedule_data = gen_schedule_data()
    schedule_data["open"]["time"] = time_str(time_morning(1))
    schedule_data["close"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    freezer.move_to(time_morning(1))
    time.sleep(0.6)

    freezer.move_to(time_morning(2))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
        ],
    )


def test_schedule_ctrl_pending_open_dup(client, mocker, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    sensor_data_mock = mocker.patch("rasp_shutter_sensor.get_sensor_data")

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "close",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    freezer.move_to(time_morning(0))
    time.sleep(0.6)

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "index": 1,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
            {"index": 1, "state": "open"},
        ],
    )

    sensor_data_mock.return_value = SENSOR_DATA_DARK

    schedule_data = gen_schedule_data()
    schedule_data["close"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    freezer.move_to(time_morning(1))
    time.sleep(0.6)

    freezer.move_to(time_morning(2))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
            {"index": 1, "state": "open"},
            {"cmd": "pending", "state": "open"},
        ],
    )

    sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

    freezer.move_to(time_morning(3))
    time.sleep(0.6)

    freezer.move_to(time_morning(4))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "close"},
            {"index": 1, "state": "close"},
            {"index": 1, "state": "open"},
            {"cmd": "pending", "state": "open"},
            {"index": 0, "state": "open"},
        ],
    )


def test_schedule_ctrl_control_fail_1(client, mocker, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    mocker.patch("app_scheduler.exec_shutter_control_impl", return_value=False)
    mocker.patch("rasp_shutter_sensor.get_sensor_data", return_value=SENSOR_DATA_DARK)

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
        ],
    )

    schedule_data = gen_schedule_data()
    schedule_data["open"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    freezer.move_to(time_evening(1))
    time.sleep(0.6)

    freezer.move_to(time_evening(2))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
        ],
    )


def test_schedule_ctrl_control_fail_2(client, mocker, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()
    mocker.patch("rasp_shutter_sensor.get_sensor_data", return_value=SENSOR_DATA_DARK)

    response = client.get(
        "/rasp-shutter/api/shutter_ctrl",
        query_string={
            "cmd": 1,
            "state": "open",
        },
    )
    assert response.status_code == 200
    assert response.json["result"] == "success"

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
        ],
    )

    mocker.patch(
        "app_scheduler.rasp_shutter_control.set_shutter_state",
        side_effect=RuntimeError(),
    )

    schedule_data = gen_schedule_data()
    schedule_data["open"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200
    time.sleep(0.6)

    freezer.move_to(time_evening(1))
    time.sleep(0.6)

    freezer.move_to(time_evening(2))
    time.sleep(0.6)

    freezer.move_to(time_evening(3))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [
            {"index": 0, "state": "open"},
            {"index": 1, "state": "open"},
        ],
    )


def test_schedule_ctrl_invalid_sensor_1(client, mocker, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    mocker.patch("slack_sdk.WebClient.chat_postMessage", return_value=True)
    sensor_data_mock = mocker.patch("rasp_shutter_sensor.get_sensor_data")

    freezer.move_to(time_morning(0))
    time.sleep(0.6)

    sensor_data = SENSOR_DATA_BRIGHT.copy()
    sensor_data["lux"] = {"valid": False, "value": 5000}
    sensor_data_mock.return_value = sensor_data

    schedule_data = gen_schedule_data()
    schedule_data["close"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    freezer.move_to(time_morning(1))
    time.sleep(0.6)

    freezer.move_to(time_morning(2))
    time.sleep(0.6)

    ctrl_log_check(
        client,
        [],
    )


def test_schedule_ctrl_invalid_sensor_2(client, mocker, freezer):
    ctrl_log_clear(client)
    ctrl_stat_clear()

    mocker.patch("slack_sdk.WebClient.chat_postMessage", return_value=True)
    sensor_data_mock = mocker.patch("rasp_shutter_sensor.get_sensor_data")

    freezer.move_to(time_morning(0))
    time.sleep(0.6)

    sensor_data = SENSOR_DATA_BRIGHT.copy()
    sensor_data["solar_rad"] = {"valid": False, "value": 5000}
    sensor_data_mock.return_value = sensor_data

    schedule_data = gen_schedule_data()
    schedule_data["close"]["is_active"] = False
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200
    time.sleep(0.6)

    freezer.move_to(time_morning(1))
    time.sleep(0.6)

    freezer.move_to(time_morning(2))
    time.sleep(0.6)

    ctrl_log_check(client, [])


def test_schedule_ctrl_read(client):
    response = client.get("/rasp-shutter/api/schedule_ctrl")
    assert response.status_code == 200
    assert len(response.json) == 2


def test_schedule_ctrl_read_fail_1(client, mocker):
    schedule_data = gen_schedule_data()
    del schedule_data["open"]

    mocker.patch("pickle.load", return_value=schedule_data)

    response = client.get("/rasp-shutter/api/schedule_ctrl")
    assert response.status_code == 200
    assert len(response.json) == 2


def test_schedule_ctrl_read_fail_2(client):
    import webapp_config

    with open(webapp_config.SCHEDULE_DATA_PATH, "wb") as f:
        f.write(b"TEST")

    response = client.get("/rasp-shutter/api/schedule_ctrl")
    assert response.status_code == 200
    assert len(response.json) == 2


def test_schedule_ctrl_write_fail(client, mocker):
    mocker.patch("pickle.dump", side_effect=RuntimeError())

    schedule_data = gen_schedule_data()
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200

    # NOTE: 次回のテストに向けて，正常なものに戻しておく
    schedule_data = gen_schedule_data()
    response = client.get(
        "/rasp-shutter/api/schedule_ctrl",
        query_string={"cmd": "set", "data": json.dumps(schedule_data)},
    )
    assert response.status_code == 200


def test_schedule_ctrl_validate_fail(client, mocker):
    mocker.patch("app_scheduler.schedule_validate", return_value=False)

    response = client.get("/rasp-shutter/api/schedule_ctrl")
    assert response.status_code == 200
    assert len(response.json) == 2


def test_shutter_list(client):
    response = client.get("/rasp-shutter/api/shutter_list")
    assert response.status_code == 200


def test_dummy_open(client):
    response = client.get("/rasp-shutter/api/dummy/open")
    assert response.status_code == 200


def test_dummy_close(client):
    response = client.get("/rasp-shutter/api/dummy/close")
    assert response.status_code == 200


def test_sensor_1(client):
    response = client.get("/rasp-shutter/api/sensor")
    assert response.status_code == 200


def test_sensor_2(client, mocker):
    mocker.patch("sensor_data.fetch_data", return_value={"valid": False})

    response = client.get("/rasp-shutter/api/sensor")
    assert response.status_code == 200

    mocker.patch(
        "sensor_data.fetch_data",
        return_value={
            "valid": True,
            "value": [0],
            "time": [datetime.datetime.now(datetime.timezone.utc)],
        },
    )

    response = client.get("/rasp-shutter/api/sensor")
    assert response.status_code == 200


def test_sensor_dummy(client, mocker):
    # NOTE: 何かがまだ足りない
    def value_mock():
        value_mock.i += 1
        if value_mock.i == 1:
            return None
        else:
            return 1

    value_mock.i = 0

    table_entry_mock = mocker.MagicMock()
    record_mock = mocker.MagicMock()
    query_api_mock = mocker.MagicMock()
    mocker.patch.object(
        record_mock,
        "get_value",
        side_effect=value_mock,
    )
    mocker.patch.object(
        record_mock,
        "get_time",
        return_value=datetime.datetime.now(datetime.timezone.utc),
    )
    table_entry_mock.__iter__.return_value = [record_mock, record_mock]
    type(table_entry_mock).records = table_entry_mock
    query_api_mock.query.return_value = [table_entry_mock]
    mocker.patch(
        "influxdb_client.InfluxDBClient.query_api",
        return_value=query_api_mock,
    )

    response = client.get("/rasp-shutter/api/sensor")
    assert response.status_code == 200


def test_sensor_fail_1(client, mocker):
    mocker.patch("influxdb_client.InfluxDBClient.query_api", side_effect=RuntimeError())

    response = client.get("/rasp-shutter/api/sensor")
    assert response.status_code == 200


def test_sensor_fail_2(client, mocker):
    mocker.patch(
        "influxdb_client.client.flux_table.FluxRecord.get_value",
        return_value=None,
    )

    response = client.get("/rasp-shutter/api/sensor")
    assert response.status_code == 200


def test_log_view(client):
    response = client.get(
        "/rasp-shutter/api/log_view",
        headers={"Accept-Encoding": "gzip"},
        query_string={
            "callback": "TEST",
        },
    )
    assert response.status_code == 200


def test_log_clear(client):
    response = client.get("/rasp-shutter/api/log_clear")
    assert response.status_code == 200

    response = client.get(
        "/rasp-shutter/api/log_view",
        headers={"Accept-Encoding": "gzip"},
        query_string={
            "callback": "TEST",
        },
    )
    assert response.status_code == 200


def test_sysinfo(client):
    response = client.get("/rasp-shutter/api/sysinfo")
    assert response.status_code == 200
    assert "date" in response.json
    assert "uptime" in response.json
    assert "loadAverage" in response.json


def test_snapshot(client):
    response = client.get("/rasp-shutter/api/snapshot")
    assert response.status_code == 200
    assert "msg" in response.json
    response = client.get("/rasp-shutter/api/snapshot")
    assert response.status_code == 200
    assert "msg" not in response.json


def test_memory(client):
    response = client.get("/rasp-shutter/api/memory")
    assert response.status_code == 200
    assert "memory" in response.json


def test_second_str():
    import rasp_shutter_control

    assert rasp_shutter_control.time_str(3600) == "1時間"
    assert rasp_shutter_control.time_str(3660) == "1時間1分"
    assert rasp_shutter_control.time_str(50) == "50秒"


def test_terminate():
    import webapp_log
    import rasp_shutter_schedule

    webapp_log.term()
    rasp_shutter_schedule.term()
    # NOTE: 二重に呼んでもエラーにならないことを確認
    webapp_log.term()
    rasp_shutter_schedule.term()
