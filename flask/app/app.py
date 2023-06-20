#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
電動シャッターの開閉を自動化するアプリのサーバーです

Usage:
  app.py [-c CONFIG] [-p PORT] [-D] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -p PORT           : WEB サーバのポートを指定します．[default: 5000]
  -D                : ダミーモードで実行します．CI テストで利用することを想定しています．
  -d                : デバッグモードで動作します．
"""

from docopt import docopt

from flask import Flask
import sys
import pathlib
import time
import logging
import atexit

if __name__ == "__main__":
    import os

    sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))
    import logger
    from config import load_config

    args = docopt(__doc__)

    config_file = args["-c"]
    port = args["-p"]
    dummy_mode = os.environ.get("DUMMY_MODE", args["-D"])
    debug_mode = args["-d"]

    if debug_mode:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logger.init("hems.rasp-shutter", level=log_level)

    # NOTE: オプションでダミーモードが指定された場合，環境変数もそれに揃えておく
    if dummy_mode:
        logging.warning("Set dummy mode")
        os.environ["DUMMY_MODE"] = "true"

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    import rasp_shutter_control
    import rasp_shutter_schedule
    import rasp_shutter_sensor

    import webapp_base
    import webapp_util
    import webapp_log
    import webapp_event

    def notify_terminate():
        webapp_log.app_log("🏃 アプリを再起動します．", eixt=True)
        # NOTE: ログを送信できるまでの時間待つ
        time.sleep(1)

    atexit.register(notify_terminate)

    app = Flask(__name__)

    app.config["CONFIG"] = load_config(config_file)
    app.config["DUMMY_MODE"] = dummy_mode

    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

    app.register_blueprint(rasp_shutter_control.blueprint)
    app.register_blueprint(rasp_shutter_schedule.blueprint)
    app.register_blueprint(rasp_shutter_sensor.blueprint)

    app.register_blueprint(webapp_base.blueprint_default)
    app.register_blueprint(webapp_base.blueprint)
    app.register_blueprint(webapp_event.blueprint)
    app.register_blueprint(webapp_log.blueprint)
    app.register_blueprint(webapp_util.blueprint)

    # app.debug = True
    # NOTE: スクリプトの自動リロード停止したい場合は use_reloader=False にする
    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=True)