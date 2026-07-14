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

import pathlib

import my_lib.healthz
import my_lib.healthz.cli


def _targets(config, args):
    return [
        my_lib.healthz.HealthzTarget(
            name=name,
            liveness_file=pathlib.Path(config["liveness"]["file"][name]),
            interval=10,
        )
        for name in ["scheduler"]
    ]


SPEC = my_lib.healthz.cli.HealthzCliSpec(
    logger_name="hems.rasp-shutter",
    targets_builder=_targets,
    use_http_port=True,
)

if __name__ == "__main__":
    assert __doc__ is not None  # noqa: S101
    my_lib.healthz.cli.run(SPEC, __doc__)
