"""
シャッター操作メトリクス収集モジュール

このモジュールは以下のメトリクスを収集し、SQLiteデータベースに保存します：
- その日に最後に開けた時刻と最後に閉じた時刻
- 前項の際の照度、日射、太陽高度
- その日に手動で開けた回数、手動で閉じた回数
- シャッター制御に失敗した回数
"""

from __future__ import annotations

import datetime
import logging
import pathlib
import sqlite3
import threading

import my_lib.sqlite_util
import my_lib.time

import rasp_shutter.type_defs

# センサーサンプルの保持期間（日）。表示は直近 7 日のみのため、無制限に増やさない。
SENSOR_SAMPLE_RETENTION_DAYS = 30

# F-8: シャッター個体別メトリクス用の列（既存 DB へのマイグレーション対象）
_SHUTTER_COLUMNS = (("shutter_index", "INTEGER"), ("shutter_name", "TEXT"))


class MetricsCollector:
    """シャッターメトリクス収集クラス"""

    def __init__(self, db_path: pathlib.Path):
        """
        コンストラクタ

        Args:
        ----
            db_path: SQLiteデータベースファイルパス

        """
        self.db_path = db_path
        self.lock = threading.Lock()
        # sensor_samples の日次クリーンアップを 1 日 1 回に抑えるための記録
        self._last_cleanup_date: str | None = None
        self._init_database()

    def _init_database(self):
        """データベース初期化"""
        with my_lib.sqlite_util.connect(self.db_path) as conn:
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
                    shutter_index INTEGER,
                    shutter_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    failure_count INTEGER DEFAULT 1,
                    timestamp TIMESTAMP NOT NULL,
                    shutter_index INTEGER,
                    shutter_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS postpone_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    date TEXT NOT NULL,
                    intended_action TEXT NOT NULL CHECK (intended_action IN ('open', 'close')),
                    trigger TEXT NOT NULL CHECK (trigger IN ('schedule', 'auto')),
                    scheduled_time TIMESTAMP,
                    reason TEXT NOT NULL,
                    lux REAL,
                    solar_rad REAL,
                    altitude REAL,
                    threshold_lux REAL,
                    threshold_solar_rad REAL,
                    threshold_altitude REAL,
                    resolved_at TIMESTAMP,
                    resolved_operation_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS sensor_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    date TEXT NOT NULL,
                    lux REAL,
                    solar_rad REAL,
                    altitude REAL,
                    context TEXT,
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

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_postpone_events_date
                ON postpone_events(date)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_postpone_events_unresolved
                ON postpone_events(date, intended_action, resolved_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sensor_samples_timestamp
                ON sensor_samples(timestamp)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sensor_samples_date
                ON sensor_samples(date)
            """)

            self._migrate_schema(conn)

            conn.commit()

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """既存 DB にシャッター個体列を追加する（無停止マイグレーション）

        新規 DB は CREATE TABLE 文に列が含まれるため、ここは既存 DB 専用の保険。
        過去の行は NULL のまま（「記録前」として扱う）。
        """
        for table in ("operation_metrics", "daily_failures"):
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for column, column_type in _SHUTTER_COLUMNS:
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
                    logging.info("Migrated %s: added column %s", table, column)

    def record_shutter_operation(
        self,
        action: str,
        mode: str,
        sensor_data: rasp_shutter.type_defs.SensorData | None = None,
        timestamp: datetime.datetime | None = None,
        shutter_index: int | None = None,
        shutter_name: str | None = None,
    ):
        """
        シャッター操作を記録

        Args:
        ----
            action: "open" または "close"
            mode: "manual", "schedule", "auto"
            sensor_data: センサーデータ（照度、日射、太陽高度など）
            timestamp: 操作時刻（指定しない場合は現在時刻）
            shutter_index: シャッターのインデックス
            shutter_name: シャッター名

        """
        if timestamp is None:
            timestamp = my_lib.time.now()

        date = timestamp.date().isoformat()

        # センサーデータを準備
        lux = None
        solar_rad = None
        altitude = None

        if sensor_data:
            if sensor_data.lux.valid:
                lux = sensor_data.lux.value
            if sensor_data.solar_rad.valid:
                solar_rad = sensor_data.solar_rad.value
            if sensor_data.altitude.valid:
                altitude = sensor_data.altitude.value

        # NOTE: INSERT + UPDATE の原子性は my_lib.sqlite_util.connect の
        # コンテキストマネージャ（成功時 commit / 例外時 rollback）で担保される
        with self.lock, my_lib.sqlite_util.connect(self.db_path) as conn:
            # 個別操作として記録
            cursor = conn.execute(
                """
                INSERT INTO operation_metrics
                (timestamp, date, action, operation_type, lux, solar_rad, altitude,
                 shutter_index, shutter_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    timestamp.isoformat(),
                    date,
                    action,
                    mode,
                    lux,
                    solar_rad,
                    altitude,
                    shutter_index,
                    shutter_name,
                ),
            )
            operation_id = cursor.lastrowid

            # 同日・同方向の未解決の見合わせを解消扱いにする
            conn.execute(
                """
                UPDATE postpone_events
                SET resolved_at = ?, resolved_operation_id = ?
                WHERE date = ? AND intended_action = ? AND resolved_at IS NULL
            """,
                (timestamp.isoformat(), operation_id, date, action),
            )

    def record_failure(
        self,
        timestamp: datetime.datetime | None = None,
        shutter_index: int | None = None,
        shutter_name: str | None = None,
    ):
        """
        シャッター制御失敗を記録

        Args:
        ----
            timestamp: 失敗時刻（指定しない場合は現在時刻）
            shutter_index: シャッターのインデックス
            shutter_name: シャッター名

        """
        if timestamp is None:
            timestamp = my_lib.time.now()

        date = timestamp.date().isoformat()

        with self.lock, my_lib.sqlite_util.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO daily_failures (date, timestamp, shutter_index, shutter_name)
                VALUES (?, ?, ?, ?)
            """,
                (date, timestamp.isoformat(), shutter_index, shutter_name),
            )

    def record_postpone(
        self,
        intended_action: str,
        trigger: str,
        reason: str,
        sensor_data: rasp_shutter.type_defs.SensorData | None = None,
        threshold: dict | None = None,
        scheduled_time: datetime.datetime | None = None,
        timestamp: datetime.datetime | None = None,
        cooldown_sec: float = 60.0,
    ) -> bool:
        """見合わせイベントを記録 (同日・同方向・同reason は cooldown_sec 以内なら抑制)

        Returns:
            実際に記録した場合 True、クールダウンで抑制された場合 False
        """
        if timestamp is None:
            timestamp = my_lib.time.now()

        date = timestamp.date().isoformat()

        lux = sensor_data.lux.value if sensor_data and sensor_data.lux.valid else None
        solar_rad = sensor_data.solar_rad.value if sensor_data and sensor_data.solar_rad.valid else None
        altitude = sensor_data.altitude.value if sensor_data and sensor_data.altitude.valid else None

        threshold_lux = threshold.get("lux") if threshold else None
        threshold_solar_rad = threshold.get("solar_rad") if threshold else None
        threshold_altitude = threshold.get("altitude") if threshold else None

        cooldown_threshold = (timestamp - datetime.timedelta(seconds=cooldown_sec)).isoformat()

        with self.lock, my_lib.sqlite_util.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 1 FROM postpone_events
                WHERE date = ? AND intended_action = ? AND reason = ?
                  AND timestamp >= ?
                LIMIT 1
            """,
                (date, intended_action, reason, cooldown_threshold),
            )
            if cursor.fetchone() is not None:
                return False

            scheduled_iso = scheduled_time.isoformat() if scheduled_time else None
            conn.execute(
                """
                INSERT INTO postpone_events
                (timestamp, date, intended_action, trigger, scheduled_time, reason,
                 lux, solar_rad, altitude,
                 threshold_lux, threshold_solar_rad, threshold_altitude)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    timestamp.isoformat(),
                    date,
                    intended_action,
                    trigger,
                    scheduled_iso,
                    reason,
                    lux,
                    solar_rad,
                    altitude,
                    threshold_lux,
                    threshold_solar_rad,
                    threshold_altitude,
                ),
            )
        return True

    def record_sensor_sample(
        self,
        sensor_data: rasp_shutter.type_defs.SensorData | None,
        context: str | None = None,
        timestamp: datetime.datetime | None = None,
    ) -> None:
        """センサーサンプルを記録"""
        if timestamp is None:
            timestamp = my_lib.time.now()

        date = timestamp.date().isoformat()

        lux = sensor_data.lux.value if sensor_data and sensor_data.lux.valid else None
        solar_rad = sensor_data.solar_rad.value if sensor_data and sensor_data.solar_rad.valid else None
        altitude = sensor_data.altitude.value if sensor_data and sensor_data.altitude.valid else None

        with self.lock, my_lib.sqlite_util.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sensor_samples
                (timestamp, date, lux, solar_rad, altitude, context)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (timestamp.isoformat(), date, lux, solar_rad, altitude, context),
            )

            # NOTE: 1 分間隔の記録で無制限に増えるのを防ぐため、日付が変わったタイミングで
            # 保持期間を過ぎた行を削除する（1 日 1 回、同一トランザクション内）
            if self._last_cleanup_date != date:
                self._last_cleanup_date = date
                cutoff = (
                    timestamp.date() - datetime.timedelta(days=SENSOR_SAMPLE_RETENTION_DAYS)
                ).isoformat()
                deleted = conn.execute("DELETE FROM sensor_samples WHERE date < ?", (cutoff,)).rowcount
                if deleted > 0:
                    logging.info("Deleted %d old sensor samples (before %s)", deleted, cutoff)

    def cleanup_old_sensor_samples(self, retention_days: int = SENSOR_SAMPLE_RETENTION_DAYS) -> int:
        """保持期間を過ぎた sensor_samples 行を削除し、削除件数を返す"""
        cutoff = (my_lib.time.now().date() - datetime.timedelta(days=retention_days)).isoformat()
        with self.lock, my_lib.sqlite_util.connect(self.db_path) as conn:
            return conn.execute("DELETE FROM sensor_samples WHERE date < ?", (cutoff,)).rowcount

    def get_operation_metrics(self, start_date: str, end_date: str) -> list:
        """
        指定期間の操作メトリクスを取得

        Args:
        ----
            start_date: 開始日（YYYY-MM-DD形式）
            end_date: 終了日（YYYY-MM-DD形式）

        Returns:
        -------
            操作メトリクスデータのリスト

        """
        with my_lib.sqlite_util.connect(self.db_path) as conn:
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
        ----
            start_date: 開始日（YYYY-MM-DD形式）
            end_date: 終了日（YYYY-MM-DD形式）

        Returns:
        -------
            失敗メトリクスデータのリスト

        """
        with my_lib.sqlite_util.connect(self.db_path) as conn:
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

    def get_all_operation_metrics(self) -> list:
        """
        全期間の操作メトリクスを取得

        Returns
        -------
        操作メトリクスデータのリスト

        """
        with my_lib.sqlite_util.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM operation_metrics
                ORDER BY timestamp
            """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_failure_metrics(self) -> list:
        """
        全期間の失敗メトリクスを取得

        Returns
        -------
        失敗メトリクスデータのリスト

        """
        with my_lib.sqlite_util.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM daily_failures
                ORDER BY timestamp
            """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_operation_metrics(self, days: int = 30) -> list:
        """
        最近N日間の操作メトリクスを取得

        Args:
        ----
            days: 取得する日数

        Returns:
        -------
            操作メトリクスデータのリスト

        """
        end_date = my_lib.time.now().date()
        start_date = end_date - datetime.timedelta(days=days)

        return self.get_operation_metrics(start_date.isoformat(), end_date.isoformat())

    def get_recent_failure_metrics(self, days: int = 30) -> list:
        """
        最近N日間の失敗メトリクスを取得

        Args:
        ----
            days: 取得する日数

        Returns:
        -------
            失敗メトリクスデータのリスト

        """
        end_date = my_lib.time.now().date()
        start_date = end_date - datetime.timedelta(days=days)

        return self.get_failure_metrics(start_date.isoformat(), end_date.isoformat())

    def get_postpone_events(self, start_date: str, end_date: str) -> list:
        """指定期間の見合わせイベントを取得"""
        with my_lib.sqlite_util.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM postpone_events
                WHERE date BETWEEN ? AND ?
                ORDER BY timestamp
            """,
                (start_date, end_date),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_postpone_events(self, days: int = 30) -> list:
        """最近N日間の見合わせイベントを取得"""
        end_date = my_lib.time.now().date()
        start_date = end_date - datetime.timedelta(days=days)
        return self.get_postpone_events(start_date.isoformat(), end_date.isoformat())

    def get_sensor_samples(self, start_date: str, end_date: str) -> list:
        """指定期間のセンサーサンプルを取得"""
        with my_lib.sqlite_util.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM sensor_samples
                WHERE date BETWEEN ? AND ?
                ORDER BY timestamp
            """,
                (start_date, end_date),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_sensor_samples(self, days: int = 7) -> list:
        """最近N日間のセンサーサンプルを取得"""
        end_date = my_lib.time.now().date()
        start_date = end_date - datetime.timedelta(days=days)
        return self.get_sensor_samples(start_date.isoformat(), end_date.isoformat())

    def get_shutter_operation_counts(self) -> list:
        """シャッター個体別の操作回数を取得（F-8）

        Returns
        -------
        {shutter_index, shutter_name, action, operation_type, count} のリスト
        （マイグレーション前の行は shutter_index / shutter_name が None）

        """
        with my_lib.sqlite_util.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT shutter_index, shutter_name, action, operation_type, COUNT(*) AS count
                FROM operation_metrics
                GROUP BY shutter_index, shutter_name, action, operation_type
            """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_shutter_failure_counts(self) -> list:
        """シャッター個体別の失敗回数を取得（F-8）"""
        with my_lib.sqlite_util.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT shutter_index, shutter_name, COUNT(*) AS count
                FROM daily_failures
                GROUP BY shutter_index, shutter_name
            """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_daily_failure_counts(self, start_date: str, end_date: str) -> list:
        """日別の失敗件数を取得（F-9）"""
        with my_lib.sqlite_util.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT date, COUNT(*) AS count
                FROM daily_failures
                WHERE date BETWEEN ? AND ?
                GROUP BY date
                ORDER BY date
            """,
                (start_date, end_date),
            )
            return [dict(row) for row in cursor.fetchall()]


# グローバルインスタンス
_collector_instance: MetricsCollector | None = None
# NOTE: スケジューラスレッド・サンプリングスレッド・Flask ワーカーから同時に初回アクセス
# されると check-then-set が競合し、別々の Lock を持つインスタンスが 2 個できてしまう
_collector_lock = threading.Lock()


def get_collector(metrics_data_path) -> MetricsCollector:
    """メトリクス収集インスタンスを取得（スレッドセーフ）"""
    global _collector_instance

    with _collector_lock:
        if _collector_instance is None:
            db_path = pathlib.Path(metrics_data_path)
            _collector_instance = MetricsCollector(db_path)
            logging.info("Metrics collector initialized: %s", db_path)
        elif _collector_instance.db_path != pathlib.Path(metrics_data_path):
            logging.warning(
                "Metrics collector already initialized with different path: %s (requested: %s)",
                _collector_instance.db_path,
                metrics_data_path,
            )

        return _collector_instance


def reset_collector():
    """グローバルコレクタインスタンスをリセット (テスト用)"""
    global _collector_instance
    with _collector_lock:
        _collector_instance = None


def record_shutter_operation(
    action: str,
    mode: str,
    metrics_data_path,
    sensor_data: rasp_shutter.type_defs.SensorData | None = None,
    timestamp: datetime.datetime | None = None,
    shutter_index: int | None = None,
    shutter_name: str | None = None,
):
    """シャッター操作を記録（便利関数）"""
    get_collector(metrics_data_path).record_shutter_operation(
        action,
        mode,
        sensor_data,
        timestamp,
        shutter_index=shutter_index,
        shutter_name=shutter_name,
    )


def record_failure(
    metrics_data_path,
    timestamp: datetime.datetime | None = None,
    shutter_index: int | None = None,
    shutter_name: str | None = None,
):
    """シャッター制御失敗を記録（便利関数）"""
    get_collector(metrics_data_path).record_failure(
        timestamp, shutter_index=shutter_index, shutter_name=shutter_name
    )


def record_postpone(
    metrics_data_path,
    intended_action: str,
    trigger: str,
    reason: str,
    sensor_data: rasp_shutter.type_defs.SensorData | None = None,
    threshold: dict | None = None,
    scheduled_time: datetime.datetime | None = None,
    timestamp: datetime.datetime | None = None,
    cooldown_sec: float = 60.0,
) -> bool:
    """見合わせイベントを記録（便利関数）"""
    return get_collector(metrics_data_path).record_postpone(
        intended_action=intended_action,
        trigger=trigger,
        reason=reason,
        sensor_data=sensor_data,
        threshold=threshold,
        scheduled_time=scheduled_time,
        timestamp=timestamp,
        cooldown_sec=cooldown_sec,
    )


def record_sensor_sample(
    metrics_data_path,
    sensor_data: rasp_shutter.type_defs.SensorData | None,
    context: str | None = None,
    timestamp: datetime.datetime | None = None,
) -> None:
    """センサーサンプルを記録（便利関数）"""
    get_collector(metrics_data_path).record_sensor_sample(sensor_data, context, timestamp)
