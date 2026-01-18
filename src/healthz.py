#!/usr/bin/env python3
"""
Liveness のチェックを行います

Usage:
  healthz.py [-c CONFIG] [-p PORT] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -p PORT           : WEB サーバのポートを指定します。[default: 5000]
  -D                : デバッグモードで動作します。
"""

import logging
import pathlib
import sys

import my_lib.healthz


def check_liveness(target_list, port=None):
    for target in target_list:
        healthz_target = my_lib.healthz.HealthzTarget(
            name=target["name"],
            liveness_file=target["liveness_file"],
            interval=target["interval"],
        )
        if not my_lib.healthz.check_liveness(healthz_target):
            return False

    if port is not None:
        return my_lib.healthz.check_http_port(port)
    else:
        return True


if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    # docstringを使用（__doc__がNoneでないことを確認）
    assert __doc__ is not None, "Module docstring is required"  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    port = args["-p"]
    debug_mode = args["-D"]

    my_lib.logger.init("hems.rasp-water", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    target_list = [
        {
            "name": name,
            "liveness_file": pathlib.Path(config["liveness"]["file"][name]),
            "interval": 10,
        }
        for name in ["scheduler"]
    ]

    if check_liveness(target_list, port):
        logging.info("OK.")
        sys.exit(0)
    else:
        sys.exit(-1)
