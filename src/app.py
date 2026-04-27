#!/usr/bin/env python3
"""
電動シャッターの開閉を自動化するアプリのサーバーです

Usage:
  app.py [-c CONFIG] [-p PORT] [-d] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -p PORT           : WEB サーバのポートを指定します。[default: 5000]
  -d                : ダミーモードで実行します。CI テストで利用することを想定しています。
  -D                : デバッグモードで動作します。
"""

import atexit
import contextlib
import logging
import os
import signal
import sys

import flask
import flask_cors
import my_lib.proc_util
import my_lib.webapp.base
import my_lib.webapp.config
import my_lib.webapp.event
import my_lib.webapp.log
import my_lib.webapp.util

import rasp_shutter.config

SCHEMA_CONFIG = "config.schema"


def term() -> None:
    import rasp_shutter.control.scheduler
    import rasp_shutter.control.webapi.schedule

    rasp_shutter.control.scheduler.term()

    # スケジュールワーカーの終了を待機（最大10秒）
    try:
        schedule_worker = rasp_shutter.control.webapi.schedule.get_worker_thread()
        if schedule_worker:
            logging.info("Waiting for schedule worker to finish...")
            schedule_worker.join(timeout=10)
            if schedule_worker.is_alive():
                logging.warning("Schedule worker did not finish within timeout")
    except Exception:
        logging.exception("Error waiting for schedule worker")

    my_lib.webapp.log.term()

    # 子プロセスを終了
    my_lib.proc_util.kill_child()

    # プロセス終了
    logging.info("Graceful shutdown completed")
    sys.exit(0)


def sig_handler(num: int, frame: object) -> None:
    logging.warning("receive signal %d", num)

    if num in (signal.SIGTERM, signal.SIGINT):
        # Flask reloader の子プロセスも含めて終了する
        try:
            # 現在のプロセスがプロセスグループリーダーの場合、全体を終了
            current_pid = os.getpid()
            pgid = os.getpgid(current_pid)
            if current_pid == pgid:
                logging.info("Terminating process group %d", pgid)
                os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            # プロセスグループ操作に失敗した場合は通常の終了処理
            pass

        term()


def create_app(config: rasp_shutter.config.AppConfig, dummy_mode: bool = False) -> flask.Flask:
    # NOTE: オプションでダミーモードが指定された場合、環境変数もそれに揃えておく
    # control.py がモジュールロード時に DUMMY_MODE を参照するため、インポート前に設定する
    if dummy_mode:
        os.environ["DUMMY_MODE"] = "true"
    else:  # pragma: no cover
        os.environ["DUMMY_MODE"] = "false"

    # NOTE: DUMMY_MODE 環境変数を設定した後にモジュールをインポート
    import rasp_shutter.control.webapi.control
    import rasp_shutter.control.webapi.schedule
    import rasp_shutter.control.webapi.sensor
    import rasp_shutter.metrics.webapi.page

    # NOTE: テストのため、環境変数 DUMMY_MODE をセットしてからロードしたいのでこの位置
    environment = rasp_shutter.config.build_environment(config)
    rasp_shutter.config.set_environment(environment)

    app = flask.Flask("rasp-shutter")

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        if dummy_mode:
            logging.warning("Set dummy mode")
        else:  # pragma: no cover
            pass

        rasp_shutter.control.webapi.control.init()
        rasp_shutter.control.webapi.schedule.init(config)
        if environment.log_file_path is None:
            raise RuntimeError("webapp.data.log_file_path is required")
        my_lib.webapp.log.init(config.slack, environment.log_file_path)

        def notify_terminate() -> None:  # pragma: no cover
            my_lib.webapp.log.info("🏃 アプリを再起動します。")
            my_lib.webapp.log.term()

        atexit.register(notify_terminate)
    else:  # pragma: no cover
        pass

    flask_cors.CORS(app)

    app.config["CONFIG"] = config
    app.config["DUMMY_MODE"] = dummy_mode

    # Flask 2.2+のJSON互換性設定。mypy/tyはJSONProviderのcompat属性を認識しないため抑制
    app.json.compat = True  # type: ignore[attr-defined,union-attr]

    url_prefix = rasp_shutter.config.URL_PREFIX

    app.register_blueprint(rasp_shutter.control.webapi.control.blueprint, url_prefix=url_prefix)
    app.register_blueprint(rasp_shutter.control.webapi.schedule.blueprint, url_prefix=url_prefix)
    app.register_blueprint(rasp_shutter.control.webapi.sensor.blueprint, url_prefix=url_prefix)
    app.register_blueprint(rasp_shutter.metrics.webapi.page.blueprint, url_prefix=url_prefix)

    app.register_blueprint(my_lib.webapp.base.create_root_redirect_blueprint(url_prefix=url_prefix))
    app.register_blueprint(
        my_lib.webapp.base.create_static_blueprint(environment=environment), url_prefix=url_prefix
    )
    app.register_blueprint(my_lib.webapp.event.blueprint, url_prefix=url_prefix)
    app.register_blueprint(my_lib.webapp.log.blueprint, url_prefix=url_prefix)
    app.register_blueprint(my_lib.webapp.util.blueprint, url_prefix=url_prefix)

    if os.environ.get("TEST") == "true":
        import rasp_shutter.control.webapi.test.sync
        import rasp_shutter.control.webapi.test.time

        app.register_blueprint(rasp_shutter.control.webapi.test.time.blueprint, url_prefix=url_prefix)
        app.register_blueprint(rasp_shutter.control.webapi.test.sync.blueprint, url_prefix=url_prefix)

    my_lib.webapp.config.show_handler_list(app)

    return app


if __name__ == "__main__":
    import pathlib

    import docopt
    import my_lib.logger

    # docstringを使用（__doc__がNoneでないことを確認）
    assert __doc__ is not None, "Module docstring is required"  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    port = args["-p"]
    dummy_mode = args["-d"]
    debug_mode = args["-D"]

    my_lib.logger.init("hems.rasp-shutter", level=logging.DEBUG if debug_mode else logging.INFO)

    config = rasp_shutter.config.load(config_file, pathlib.Path(SCHEMA_CONFIG))

    app = create_app(config, dummy_mode)

    # プロセスグループリーダーとして実行（リローダープロセスの適切な管理のため）
    with contextlib.suppress(PermissionError):
        os.setpgrp()

    # シグナルハンドラを登録（Kubernetes rollout時のSIGTERMに対応）
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    # 異常終了時のクリーンアップ処理を登録
    def cleanup_on_exit() -> None:
        try:
            current_pid = os.getpid()
            pgid = os.getpgid(current_pid)
            if current_pid == pgid:
                # プロセスグループ内の他のプロセスを終了
                os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass

    atexit.register(cleanup_on_exit)

    # Flaskアプリケーションを実行
    try:
        # NOTE: スクリプトの自動リロード停止したい場合は use_reloader=False にする
        app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=True)  # noqa: S104
    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt, shutting down...")
        sig_handler(signal.SIGINT, None)
