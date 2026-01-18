#!/usr/bin/env python3
"""
rasp-shutter 制御用設定定数

時間定数、パス定数など制御に関わる設定を集約管理します。
"""

import pathlib

import my_lib.webapp.config


def _get_stat_dir_path() -> pathlib.Path:
    """STAT_DIR_PATHを取得（Noneの場合はデフォルトパスを返す）"""
    if my_lib.webapp.config.STAT_DIR_PATH is not None:
        return my_lib.webapp.config.STAT_DIR_PATH
    return pathlib.Path("data")


# ======================================================================
# パス定数
# ======================================================================
_stat_dir = _get_stat_dir_path()
STAT_PENDING_OPEN = _stat_dir / "pending" / "open"
STAT_AUTO_CLOSE = _stat_dir / "auto" / "close"

# ======================================================================
# 時間帯定数（時）
# ======================================================================
# 朝の開始時刻
HOUR_MORNING_START = 5
# 自動で開ける処理の終了時刻
HOUR_AUTO_OPEN_END = 12
# 暗くて延期されていた開け制御の終了時刻
HOUR_PENDING_OPEN_END = 13
# 自動で閉める処理の終了時刻
HOUR_AUTO_CLOSE_END = 20

# ======================================================================
# 経過時間定数（秒）
# ======================================================================
# 暗くて開けるのを延期中と判定する最大経過時間（6時間）
ELAPSED_PENDING_OPEN_MAX_SEC = 6 * 60 * 60
# 自動で閉めた履歴の有効期間（12時間）
ELAPSED_AUTO_CLOSE_MAX_SEC = 12 * 60 * 60

# ======================================================================
# 制御間隔定数
# ======================================================================
# この時間（分）内では自動制御で開閉しない
EXEC_INTERVAL_AUTO_MIN = 2
# この時間（時間）内に同じ制御がスケジューラで再度リクエストされた場合、実行をやめる
EXEC_INTERVAL_SCHEDULE_HOUR = 12
# この時間（分）内に同じ制御が手動で再度リクエストされた場合、実行をやめる
EXEC_INTERVAL_MANUAL_MINUTES = 1


# ======================================================================
# デフォルトスケジュール値
# ======================================================================
DEFAULT_OPEN_TIME = "08:00"
DEFAULT_CLOSE_TIME = "17:00"
DEFAULT_OPEN_SOLAR_RAD = 150
DEFAULT_OPEN_LUX = 1000
DEFAULT_CLOSE_SOLAR_RAD = 80
DEFAULT_CLOSE_LUX = 1200


# ======================================================================
# パス生成関数
# ======================================================================
def get_exec_stat_path(state: str, index: int) -> pathlib.Path:
    """制御実行状態ファイルのパスを取得

    Args:
    ----
        state: シャッター状態 ("open" または "close")
        index: シャッターのインデックス

    Returns:
    -------
        pathlib.Path: 状態ファイルのパス

    """
    return _stat_dir / "exe" / f"{index}_{state}"
