#!/usr/bin/env python3
"""テスト状態管理

テストの状態管理とクリーンアップを提供します。
"""

from typing import TYPE_CHECKING

import my_lib.footprint
import my_lib.notify.slack
import my_lib.webapp.config
import my_lib.webapp.log

if TYPE_CHECKING:
    import rasp_shutter.config


class StateManager:
    """テスト状態マネージャー"""

    def __init__(self, config: "rasp_shutter.config.AppConfig"):
        self.config = config

    def reset_all(self) -> None:
        """すべての状態をリセット"""
        self.clear_liveness()
        self.clear_control_stats()
        self.clear_slack_history()
        self.clear_logs()

    def clear_liveness(self) -> None:
        """Liveness ファイルをクリア"""
        my_lib.footprint.clear(self.config.liveness.file.scheduler)

    def clear_control_stats(self) -> None:
        """制御統計をクリア"""
        import rasp_shutter.control.config
        import rasp_shutter.control.webapi.control

        rasp_shutter.control.webapi.control.clean_stat_exec(self.config)
        rasp_shutter.control.config.STAT_AUTO_CLOSE.unlink(missing_ok=True)
        rasp_shutter.control.config.STAT_PENDING_OPEN.unlink(missing_ok=True)

    def clear_slack_history(self) -> None:
        """Slack通知履歴をクリア"""
        my_lib.notify.slack._interval_clear()
        my_lib.notify.slack._hist_clear()

    def clear_logs(self) -> None:
        """ログをクリア"""
        import contextlib

        with contextlib.suppress(Exception):
            my_lib.webapp.log.clear()

    def clear_schedule_file(self) -> None:
        """スケジュールファイルをクリア"""
        import os

        worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
        original_schedule_path = my_lib.webapp.config.SCHEDULE_FILE_PATH
        if original_schedule_path is not None:
            worker_schedule_path = original_schedule_path.parent / f"schedule_{worker_id}.dat"
            my_lib.webapp.config.SCHEDULE_FILE_PATH = worker_schedule_path
            worker_schedule_path.unlink(missing_ok=True)

    def reset_metrics_collector(self) -> None:
        """メトリクスコレクターをリセット"""
        import rasp_shutter.metrics.collector

        rasp_shutter.metrics.collector.reset_collector()


def get_worker_id() -> str:
    """pytest-xdistのワーカーIDを取得

    Returns:
        ワーカーID（"main" または "gw0", "gw1", ...）
    """
    import os

    return os.environ.get("PYTEST_XDIST_WORKER", "main")


def get_worker_schedule_path():
    """ワーカー固有のスケジュールファイルパスを取得

    Returns:
        スケジュールファイルのパス
    """
    worker_id = get_worker_id()
    original_path = my_lib.webapp.config.SCHEDULE_FILE_PATH
    if original_path is not None:
        return original_path.parent / f"schedule_{worker_id}.dat"
    return None
