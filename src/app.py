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
import logging
import os
import pathlib

import flask
import my_lib.webapp.base
import my_lib.webapp.config
import my_lib.webapp.event
import my_lib.webapp.log
import my_lib.webapp.runner
import my_lib.webapp.util

import rasp_shutter.config

SCHEMA_CONFIG = "config.schema"


def _shutdown() -> None:
    """スケジューラ等を停止する (my_lib.webapp.runner の term フック)"""
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


SPEC = my_lib.webapp.runner.WebAppSpec(
    logger_name="hems.rasp-shutter",
    config_loader=lambda config_file, args: rasp_shutter.config.load(
        config_file, pathlib.Path(SCHEMA_CONFIG)
    ),
    app_factory=lambda config, ctx: create_app(config, ctx.dummy_mode),
    term_hooks=(_shutdown,),
)

if __name__ == "__main__":
    assert __doc__ is not None, "Module docstring is required"  # noqa: S101
    my_lib.webapp.runner.run(SPEC, __doc__)
