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
from typing import Dict, Optional

import my_lib.webapp.config


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
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    last_open_time TIMESTAMP,
                    last_close_time TIMESTAMP,
                    last_open_lux REAL,
                    last_open_solar_rad REAL,
                    last_open_altitude REAL,
                    last_close_lux REAL,
                    last_close_solar_rad REAL,
                    last_close_altitude REAL,
                    manual_open_count INTEGER DEFAULT 0,
                    manual_close_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_metrics_date
                ON daily_metrics(date)
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS update_daily_metrics_timestamp
                AFTER UPDATE ON daily_metrics
                BEGIN
                    UPDATE daily_metrics SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = NEW.id;
                END
            """)

    def _get_today_date(self) -> str:
        """今日の日付を文字列で取得"""
        return datetime.date.today().isoformat()

    def _get_or_create_daily_record(self, conn: sqlite3.Connection, date: str) -> int:
        """指定日のレコードを取得または作成"""
        cursor = conn.execute("SELECT id FROM daily_metrics WHERE date = ?", (date,))
        row = cursor.fetchone()

        if row:
            return row[0]

        cursor = conn.execute("INSERT INTO daily_metrics (date) VALUES (?)", (date,))
        return cursor.lastrowid

    def record_shutter_operation(
        self,
        action: str,
        mode: str,
        sensor_data: Optional[Dict] = None,
        timestamp: Optional[datetime.datetime] = None,
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

        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                record_id = self._get_or_create_daily_record(conn, date)

                # 最後の操作時刻を更新
                if action == "open":
                    update_fields = ["last_open_time = ?"]
                    params = [timestamp]

                    if sensor_data:
                        if sensor_data.get("lux", {}).get("valid"):
                            update_fields.append("last_open_lux = ?")
                            params.append(sensor_data["lux"]["value"])

                        if sensor_data.get("solar_rad", {}).get("valid"):
                            update_fields.append("last_open_solar_rad = ?")
                            params.append(sensor_data["solar_rad"]["value"])

                        if sensor_data.get("altitude", {}).get("valid"):
                            update_fields.append("last_open_altitude = ?")
                            params.append(sensor_data["altitude"]["value"])

                    # 手動操作の場合はカウンタを増加
                    if mode == "manual":
                        update_fields.append("manual_open_count = manual_open_count + 1")

                elif action == "close":
                    update_fields = ["last_close_time = ?"]
                    params = [timestamp]

                    if sensor_data:
                        if sensor_data.get("lux", {}).get("valid"):
                            update_fields.append("last_close_lux = ?")
                            params.append(sensor_data["lux"]["value"])

                        if sensor_data.get("solar_rad", {}).get("valid"):
                            update_fields.append("last_close_solar_rad = ?")
                            params.append(sensor_data["solar_rad"]["value"])

                        if sensor_data.get("altitude", {}).get("valid"):
                            update_fields.append("last_close_altitude = ?")
                            params.append(sensor_data["altitude"]["value"])

                    # 手動操作の場合はカウンタを増加
                    if mode == "manual":
                        update_fields.append("manual_close_count = manual_close_count + 1")

                params.append(record_id)

                conn.execute(f"UPDATE daily_metrics SET {', '.join(update_fields)} WHERE id = ?", params)

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
                record_id = self._get_or_create_daily_record(conn, date)

                conn.execute(
                    "UPDATE daily_metrics SET failure_count = failure_count + 1 WHERE id = ?", (record_id,)
                )

    def get_daily_metrics(self, date: str) -> Optional[Dict]:
        """
        指定日のメトリクスを取得

        Args:
            date: 日付（YYYY-MM-DD形式）

        Returns:
            メトリクスデータまたはNone
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM daily_metrics WHERE date = ?", (date,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def get_metrics_range(self, start_date: str, end_date: str) -> list:
        """
        指定期間のメトリクスを取得

        Args:
            start_date: 開始日（YYYY-MM-DD形式）
            end_date: 終了日（YYYY-MM-DD形式）

        Returns:
            メトリクスデータのリスト
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM daily_metrics
                WHERE date BETWEEN ? AND ?
                ORDER BY date
                """,
                (start_date, end_date),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_metrics(self, days: int = 30) -> list:
        """
        最近N日間のメトリクスを取得

        Args:
            days: 取得する日数

        Returns:
            メトリクスデータのリスト
        """
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days)

        return self.get_metrics_range(start_date.isoformat(), end_date.isoformat())


# グローバルインスタンス
_collector_instance: Optional[MetricsCollector] = None


def get_collector(metrics_data_path=None) -> MetricsCollector:
    """メトリクス収集インスタンスを取得"""
    global _collector_instance

    if _collector_instance is None:
        if metrics_data_path:
            db_path = Path(metrics_data_path)
        else:
            db_path = my_lib.webapp.config.DATA_DIR_PATH / "metrics.db"
        _collector_instance = MetricsCollector(db_path)
        logging.info("Metrics collector initialized: %s", db_path)

    return _collector_instance


def record_shutter_operation(
    action: str, 
    mode: str, 
    metrics_data_path=None,
    sensor_data: Optional[Dict] = None, 
    timestamp: Optional[datetime.datetime] = None
):
    """シャッター操作を記録（便利関数）"""
    get_collector(metrics_data_path).record_shutter_operation(action, mode, sensor_data, timestamp)


def record_failure(metrics_data_path=None, timestamp: Optional[datetime.datetime] = None):
    """シャッター制御失敗を記録（便利関数）"""
    get_collector(metrics_data_path).record_failure(timestamp)
