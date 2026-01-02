#!/usr/bin/env python3
import contextlib
import logging
import os
import pathlib
import signal
import subprocess
import time

import pytest
import requests


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
        preexec_fn=os.setsid,  # noqa: PLW1509
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
