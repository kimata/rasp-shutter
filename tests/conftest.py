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
        ["/usr/bin/env", "uv", "run", "python", "src/app.py", "-d", "-p", str(port)],
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
            "DUMMY_MODE": "true",
        },
    ) as fixture:
        yield fixture


# === 要因分離テスト用フィクスチャ ===
# 環境変数で有効化: ISOLATE_LOG=true, ISOLATE_SQLITE=true, ISOLATE_FILEIO=true


@pytest.fixture(scope="session", autouse=True)
def isolate_log_system():
    """ログシステム (my_lib.webapp.log) の SyncManager を無効化

    SyncManager を使用しないバージョンのログシステムに置き換えて、
    SyncManager が不安定性の原因かどうかを確認する。
    """
    import os

    if os.environ.get("ISOLATE_LOG") != "true":
        yield
        return

    # SyncManager の初期化をスキップする（_init_impl を no-op にする）
    with unittest.mock.patch("my_lib.webapp.log._manager._init_impl", return_value=None):
        yield


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


@pytest.fixture(scope="session", autouse=True)
def sensor_data_mock():
    """センサーデータ取得をセッションレベルでモック

    テスト間のギャップでスケジューラスレッドが get_sensor_data() を呼び出した際に、
    モックされていないInfluxDB HTTPリクエストがブロックするのを防ぐ。

    個別のテストは mock_sensor_data フィクスチャで戻り値をカスタマイズできる。
    """
    from tests.fixtures.sensor_factory import SensorDataFactory

    # デフォルトは明るい状態を返す
    default_data = SensorDataFactory.bright()

    with unittest.mock.patch(
        "rasp_shutter.control.webapi.sensor.get_sensor_data",
        return_value=default_data,
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session")
def config():
    """設定を読み込む"""
    import rasp_shutter.config

    return rasp_shutter.config.load(CONFIG_FILE, pathlib.Path(SCHEMA_CONFIG))


@pytest.fixture(autouse=True)
def _clear(app, config):  # app is dependency only, not used directly
    """各テスト前に状態をクリア

    NOTE: app fixtureに依存することで、ワーカー固有のパス設定が
    この fixture より先に実行されることを保証する。
    app 引数は直接使用しないが、fixture実行順序の制御に必要。
    """
    import my_lib.footprint
    import my_lib.notify.slack
    import my_lib.webapp.config

    # NOTE: my_lib.webapp.config.init() は app fixture で既に呼ばれている
    # ワーカー固有のパスも app fixture で設定済みなので、ここでは呼ばない
    # rasp_shutter.control.config は動的にパスを評価するため、ここでのインポートは不要
    # init()後にインポートする必要があるモジュール
    import rasp_shutter.control.config
    import rasp_shutter.control.scheduler
    import rasp_shutter.metrics.collector

    my_lib.footprint.clear(config.liveness.file.scheduler)

    # Clear scheduler jobs to prevent test interference
    # NOTE: スケジューラのジョブはセッションスコープで共有されるため、
    # 各テスト前にクリアして前のテストのスケジュールが影響しないようにする
    rasp_shutter.control.scheduler.clear_scheduler_jobs()

    # Clear schedule file to ensure clean state for each test
    # NOTE: ワーカー固有のパスは app fixture で設定済み
    if my_lib.webapp.config.SCHEDULE_FILE_PATH is not None:
        my_lib.webapp.config.SCHEDULE_FILE_PATH.unlink(missing_ok=True)

    my_lib.notify.slack._interval_clear()
    my_lib.notify.slack._hist_clear()

    # Clear stat files
    import rasp_shutter.control.webapi.control

    rasp_shutter.control.webapi.control.clean_stat_exec(config)
    rasp_shutter.control.config.STAT_AUTO_CLOSE.unlink(missing_ok=True)
    rasp_shutter.control.config.STAT_PENDING_OPEN.unlink(missing_ok=True)

    # Clear control log (worker-specific)
    rasp_shutter.control.webapi.control._clear_cmd_hist()

    # Reset metrics collector singleton to prevent database connection leaks
    rasp_shutter.metrics.collector.reset_collector()

    # Clear webapp logs to reduce database connection warnings
    import my_lib.webapp.log

    with contextlib.suppress(Exception):
        my_lib.webapp.log.clear()


@pytest.fixture(scope="session")
def app(config):
    """Flaskアプリを作成"""
    import dataclasses

    import my_lib.webapp.config
    import my_lib.webapp.log

    import rasp_shutter.config
    from app import create_app

    # ワーカー固有のパスを設定（並列テスト実行時の競合を回避）
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")

    # メトリクスDBパスをワーカー固有に変更（SQLiteロック競合を回避）
    # NOTE: frozen dataclassなのでdataclasses.replaceで新しいconfigを作成
    original_metrics_path = config.metrics.data
    worker_metrics_path = original_metrics_path.parent / f"metrics_{worker_id}.db"
    worker_metrics_path.parent.mkdir(parents=True, exist_ok=True)
    new_metrics = dataclasses.replace(config.metrics, data=worker_metrics_path)
    config = dataclasses.replace(config, metrics=new_metrics)

    # NOTE: rasp_shutter.control.webapi.scheduleはmy_lib.webapp.config.init()の後にインポート
    my_lib.webapp.config.init(rasp_shutter.config.to_my_lib_webapp_config(config))

    # ワーカー固有のパスを設定（init()後に上書き）
    if my_lib.webapp.config.SCHEDULE_FILE_PATH is not None:
        original_path = my_lib.webapp.config.SCHEDULE_FILE_PATH
        worker_schedule_path = original_path.parent / f"schedule_{worker_id}.dat"
        # 親ディレクトリを作成（存在しない場合）
        worker_schedule_path.parent.mkdir(parents=True, exist_ok=True)
        my_lib.webapp.config.SCHEDULE_FILE_PATH = worker_schedule_path

    if my_lib.webapp.config.LOG_DIR_PATH is not None:
        original_path = my_lib.webapp.config.LOG_DIR_PATH
        worker_log_path = original_path.parent / f"log_{worker_id}.db"
        # 親ディレクトリを作成（存在しない場合）
        worker_log_path.parent.mkdir(parents=True, exist_ok=True)
        my_lib.webapp.config.LOG_DIR_PATH = worker_log_path

    if my_lib.webapp.config.STAT_DIR_PATH is not None:
        original_path = my_lib.webapp.config.STAT_DIR_PATH
        worker_stat_path = original_path.parent / f"rasp-shutter-{worker_id}"
        worker_stat_path.mkdir(parents=True, exist_ok=True)
        my_lib.webapp.config.STAT_DIR_PATH = worker_stat_path

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
    # NOTE: time.perf_counter() を使用（time_machine の影響を受けない）
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < 5.0:
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
def mock_sensor_data(sensor_data_mock):
    """センサーデータをモックするfixture

    セッションスコープの sensor_data_mock の戻り値をテストごとにカスタマイズする。
    テスト終了時に自動的にデフォルト値に戻される。
    """
    from tests.fixtures.sensor_factory import SensorDataFactory

    # テスト開始時のデフォルト値を保存
    original_return_value = sensor_data_mock.return_value

    def _mock(initial_value=None):
        if initial_value is None:
            initial_value = SensorDataFactory.bright()

        # セッションスコープのモックの戻り値を変更
        sensor_data_mock.return_value = initial_value
        return sensor_data_mock

    yield _mock

    # テスト終了時にデフォルト値に戻す
    sensor_data_mock.return_value = original_return_value
