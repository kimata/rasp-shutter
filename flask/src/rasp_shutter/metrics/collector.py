"""
シャッター操作メトリクス収集モジュール

このモジュールは以下のメトリクスを収集し、SQLiteデータベースに保存します：
- その日に最後に開けた時刻と最後に閉じた時刻
- 前項の際の照度、日射、太陽高度
- その日に手動で開けた回数、手動で閉じた回数
- シャッター制御に失敗した回数
"""

import datetime
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional


class MetricsCollector:
    """シャッターメトリクス収集クラス"""

    def __init__(self, db_path: Path):
        """
        Args:
            db_path: SQLiteデータベースファイルパス

        """
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_database()

    def _init_database(self):
        """データベース初期化"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS operation_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    date TEXT NOT NULL,
                    action TEXT NOT NULL CHECK (action IN ('open', 'close')),
                    operation_type TEXT NOT NULL CHECK (operation_type IN ('manual', 'schedule', 'auto')),
                    lux REAL,
                    solar_rad REAL,
                    altitude REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    failure_count INTEGER DEFAULT 1,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_operation_metrics_date
                ON operation_metrics(date)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_operation_metrics_type
                ON operation_metrics(operation_type, action)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_failures_date
                ON daily_failures(date)
            """)

    def _get_today_date(self) -> str:
        """今日の日付を文字列で取得"""
        return datetime.date.today().isoformat()

    def record_shutter_operation(
        self,
        action: str,
        mode: str,
        sensor_data: dict | None = None,
        timestamp: datetime.datetime | None = None,
    ):
        """
        シャッター操作を記録

        Args:
            action: "open" または "close"
            mode: "manual", "schedule", "auto"
            sensor_data: センサーデータ（照度、日射、太陽高度など）
            timestamp: 操作時刻（指定しない場合は現在時刻）

        """
        if timestamp is None:
            timestamp = datetime.datetime.now()

        date = timestamp.date().isoformat()

        # センサーデータを準備
        lux = None
        solar_rad = None
        altitude = None

        if sensor_data:
            if sensor_data.get("lux", {}).get("valid"):
                lux = sensor_data["lux"]["value"]
            if sensor_data.get("solar_rad", {}).get("valid"):
                solar_rad = sensor_data["solar_rad"]["value"]
            if sensor_data.get("altitude", {}).get("valid"):
                altitude = sensor_data["altitude"]["value"]

        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                # 個別操作として記録
                conn.execute(
                    """
                    INSERT INTO operation_metrics
                    (timestamp, date, action, operation_type, lux, solar_rad, altitude)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (timestamp, date, action, mode, lux, solar_rad, altitude),
                )

    def record_failure(self, timestamp: Optional[datetime.datetime] = None):
        """
        シャッター制御失敗を記録

        Args:
            timestamp: 失敗時刻（指定しない場合は現在時刻）
        """
        if timestamp is None:
            timestamp = datetime.datetime.now()

        date = timestamp.date().isoformat()

        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO daily_failures (date, timestamp)
                    VALUES (?, ?)
                """,
                    (date, timestamp),
                )

    def get_operation_metrics(self, start_date: str, end_date: str) -> list:
        """
        指定期間の操作メトリクスを取得

        Args:
            start_date: 開始日（YYYY-MM-DD形式）
            end_date: 終了日（YYYY-MM-DD形式）

        Returns:
            操作メトリクスデータのリスト
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM operation_metrics
                WHERE date BETWEEN ? AND ?
                ORDER BY timestamp
            """,
                (start_date, end_date),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_failure_metrics(self, start_date: str, end_date: str) -> list:
        """
        指定期間の失敗メトリクスを取得

        Args:
            start_date: 開始日（YYYY-MM-DD形式）
            end_date: 終了日（YYYY-MM-DD形式）

        Returns:
            失敗メトリクスデータのリスト
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM daily_failures
                WHERE date BETWEEN ? AND ?
                ORDER BY timestamp
            """,
                (start_date, end_date),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_operation_metrics(self, days: int = 30) -> list:
        """
        最近N日間の操作メトリクスを取得

        Args:
            days: 取得する日数

        Returns:
            操作メトリクスデータのリスト
        """
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days)

        return self.get_operation_metrics(start_date.isoformat(), end_date.isoformat())

    def get_recent_failure_metrics(self, days: int = 30) -> list:
        """
        最近N日間の失敗メトリクスを取得

        Args:
            days: 取得する日数

        Returns:
            失敗メトリクスデータのリスト
        """
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days)

        return self.get_failure_metrics(start_date.isoformat(), end_date.isoformat())


# グローバルインスタンス
_collector_instance: Optional[MetricsCollector] = None


def get_collector(metrics_data_path) -> MetricsCollector:
    """メトリクス収集インスタンスを取得"""
    global _collector_instance

    if _collector_instance is None:
        db_path = Path(metrics_data_path)
        _collector_instance = MetricsCollector(db_path)
        logging.info("Metrics collector initialized: %s", db_path)

    return _collector_instance


def record_shutter_operation(
    action: str,
    mode: str,
    metrics_data_path,
    sensor_data: Optional[Dict] = None,
    timestamp: Optional[datetime.datetime] = None,
):
    """シャッター操作を記録（便利関数）"""
    get_collector(metrics_data_path).record_shutter_operation(action, mode, sensor_data, timestamp)


def record_failure(metrics_data_path, timestamp: Optional[datetime.datetime] = None):
    """シャッター制御失敗を記録（便利関数）"""
    get_collector(metrics_data_path).record_failure(timestamp)
