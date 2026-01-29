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
        my_lib.healthz.HealthzTarget(
            name=name,
            liveness_file=pathlib.Path(config["liveness"]["file"][name]),
            interval=10,
        )
        for name in ["scheduler"]
    ]

    failed_targets = my_lib.healthz.check_liveness_all_with_ports(
        target_list,
        http_port=port,
    )

    if not failed_targets:
        logging.info("OK.")
        sys.exit(0)
    else:
        sys.exit(-1)
