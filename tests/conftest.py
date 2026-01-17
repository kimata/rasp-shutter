#!/usr/bin/env python3
# ruff: noqa: S101
"""共通fixture定義"""

import contextlib
import logging
import os
import pathlib
import signal
import subprocess
import time
import unittest
import unittest.mock

import pytest
import requests

CONFIG_FILE = "config.example.yaml"
SCHEMA_CONFIG = "config.schema"


def pytest_addoption(parser):
    parser.addoption("--host", default="127.0.0.1")
    parser.addoption("--port", default="5000")
    parser.addoption(
        "--start-server",
        action="store_true",
        default=False,
        help="Start the web server automatically for Playwright tests",
    )


@pytest.fixture
def host(request):
    return request.config.getoption("--host")


@pytest.fixture
def port(request):
    return request.config.getoption("--port")


@pytest.fixture(scope="session")
def webserver(request):
    """Start the web server for Playwright tests if --start-server option is provided."""
    if not request.config.getoption("--start-server"):
        yield None
        return

    host = request.config.getoption("--host")
    port = request.config.getoption("--port")

    # Change to project root directory
    project_root = pathlib.Path(__file__).parent.parent
    os.chdir(project_root)

    # Start the server process in DUMMY_MODE and TEST mode
    env = os.environ.copy()
    env["DUMMY_MODE"] = "true"
    env["TEST"] = "true"

    server_process = subprocess.Popen(  # noqa: S603
        ["/usr/bin/env", "uv", "run", "python", "flask/src/app.py", "-d", "-p", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        # Create new process group for proper cleanup
        preexec_fn=os.setsid,
    )

    # Wait for server to start
    app_url = f"http://{host}:{port}/rasp-shutter/"
    timeout_sec = 60
    start_time = time.time()

    while time.time() - start_time < timeout_sec:
        try:
            response = requests.get(app_url, timeout=5)
            if response.ok:
                logging.info("Server started successfully at %s", app_url)
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
    else:
        # Server failed to start, terminate process and get logs
        server_process.terminate()
        stdout, stderr = server_process.communicate(timeout=5)
        error_msg = (
            f"Server failed to start within {timeout_sec} seconds.\nStdout: {stdout}\nStderr: {stderr}"
        )
        raise RuntimeError(error_msg)

    yield server_process

    # Cleanup: gracefully terminate the entire process group
    try:
        # Send SIGTERM to the entire process group (including reloader children)
        os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
        # Wait for graceful shutdown
        server_process.wait(timeout=10)
    except (subprocess.TimeoutExpired, ProcessLookupError):
        # If graceful shutdown fails or process already gone, try force kill
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(server_process.pid), signal.SIGKILL)
        # Ensure subprocess handle is cleaned up
        with contextlib.suppress(subprocess.TimeoutExpired):
            server_process.wait(timeout=5)


@pytest.fixture
def page(page):
    from playwright.sync_api import expect

    timeout = 20000
    page.set_default_navigation_timeout(timeout)
    page.set_default_timeout(timeout)
    expect.set_options(timeout=timeout)

    return page


@pytest.fixture
def browser_context_args(browser_context_args, request):
    """環境変数 RECORD_VIDEO=true でビデオ録画を有効化"""
    args = {**browser_context_args}

    if os.environ.get("RECORD_VIDEO", "").lower() == "true":
        video_dir = pathlib.Path("reports/videos") / request.node.name
        video_dir.mkdir(parents=True, exist_ok=True)
        args["record_video_dir"] = str(video_dir)
        args["record_video_size"] = {"width": 2400, "height": 1600}

    return args


# ============================================================
# 以下はFlaskアプリのテスト用fixture
# ============================================================


@pytest.fixture(scope="session", autouse=True)
def env_mock():
    """環境変数をモック"""
    with unittest.mock.patch.dict(
        "os.environ",
        {
            "TEST": "true",
            "NO_COLORED_LOGS": "true",
        },
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session", autouse=True)
def slack_mock():
    """Slack APIをモック"""
    with (
        unittest.mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.chat_postMessage",
            return_value={"ok": True, "ts": "1234567890.123456"},
        ),
        unittest.mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.files_upload_v2",
            return_value={"ok": True, "files": [{"id": "test_file_id"}]},
        ),
        unittest.mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.files_getUploadURLExternal",
            return_value={"ok": True, "upload_url": "https://example.com"},
        ) as fixture,
    ):
        yield fixture


@pytest.fixture(scope="session")
def config():
    """設定を読み込む"""
    import rasp_shutter.config

    return rasp_shutter.config.load(CONFIG_FILE, pathlib.Path(SCHEMA_CONFIG))


@pytest.fixture(autouse=True)
def _clear(config):
    """各テスト前に状態をクリア"""
    import my_lib.footprint
    import my_lib.notify.slack
    import my_lib.webapp.config
    import rasp_shutter.config

    # NOTE: 最初にmy_lib.webapp.config.init()を呼び出す必要がある
    # rasp_shutter.control.configがmy_lib.webapp.config.STAT_DIR_PATHを参照するため
    my_lib.webapp.config.init(rasp_shutter.config.to_my_lib_webapp_config(config))

    # init()後にインポートする必要があるモジュール
    import rasp_shutter.control.config
    import rasp_shutter.metrics.collector

    my_lib.footprint.clear(config.liveness.file.scheduler)

    # Clear schedule file to ensure clean state for each test
    # Use worker-specific schedule file paths for parallel execution
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    original_schedule_path = my_lib.webapp.config.SCHEDULE_FILE_PATH
    if original_schedule_path is not None:
        worker_schedule_path = original_schedule_path.parent / f"schedule_{worker_id}.dat"
        my_lib.webapp.config.SCHEDULE_FILE_PATH = worker_schedule_path
        worker_schedule_path.unlink(missing_ok=True)

    my_lib.notify.slack._interval_clear()
    my_lib.notify.slack._hist_clear()

    # Clear stat files
    import rasp_shutter.control.webapi.control

    rasp_shutter.control.webapi.control.clean_stat_exec(config)
    rasp_shutter.control.config.STAT_AUTO_CLOSE.unlink(missing_ok=True)

    # Reset metrics collector singleton to prevent database connection leaks
    rasp_shutter.metrics.collector.reset_collector()

    # Clear webapp logs to reduce database connection warnings
    import my_lib.webapp.log

    with contextlib.suppress(Exception):
        my_lib.webapp.log.clear()


@pytest.fixture(scope="session")
def app(config):
    """Flaskアプリを作成"""
    import my_lib.webapp.config
    import my_lib.webapp.log
    import rasp_shutter.config
    from app import create_app

    # NOTE: rasp_shutter.control.webapi.scheduleはmy_lib.webapp.config.init()の後にインポート
    my_lib.webapp.config.init(rasp_shutter.config.to_my_lib_webapp_config(config))

    # init()後にインポートする必要があるモジュール
    import rasp_shutter.control.webapi.schedule

    with unittest.mock.patch.dict("os.environ", {"WERKZEUG_RUN_MAIN": "true"}):
        if my_lib.webapp.config.SCHEDULE_FILE_PATH is not None:
            my_lib.webapp.config.SCHEDULE_FILE_PATH.unlink(missing_ok=True)

        app = create_app(config, dummy_mode=True)

        with app.app_context():
            yield app

        # Cleanup
        my_lib.webapp.log.term()
        rasp_shutter.control.webapi.schedule.term()


@pytest.fixture
def client(app):
    """テストクライアントを作成"""
    import my_lib.webapp.config

    test_client = app.test_client()

    time.sleep(0.1)

    # Clear logs
    response = test_client.get(f"{my_lib.webapp.config.URL_PREFIX}/api/log_clear")
    assert response.status_code == 200

    # Wait for clear to complete
    start_time = time.time()
    while time.time() - start_time < 5.0:
        response = test_client.get(f"{my_lib.webapp.config.URL_PREFIX}/api/log_view")
        if response.status_code == 200:
            log_list = response.json["data"]
            if len(log_list) >= 1 and "クリアされました" in log_list[0]["message"]:
                break
        time.sleep(0.2)

    # Clear ctrl log
    response = test_client.get(
        f"{my_lib.webapp.config.URL_PREFIX}/api/ctrl/log",
        query_string={"cmd": "clear"},
    )
    assert response.status_code == 200

    yield test_client

    test_client.delete()


@pytest.fixture
def mock_sensor_data(mocker):
    """センサーデータをモックするfixture"""
    from tests.fixtures.sensor_factory import SensorDataFactory

    def _mock(initial_value=None):
        if initial_value is None:
            initial_value = SensorDataFactory.bright()

        sensor_mock = mocker.patch("rasp_shutter.control.webapi.sensor.get_sensor_data")
        sensor_mock.return_value = initial_value
        mocker.patch(
            "rasp_shutter.control.scheduler.rasp_shutter.control.webapi.sensor.get_sensor_data",
            side_effect=lambda _: sensor_mock.return_value,
        )
        return sensor_mock

    return _mock
