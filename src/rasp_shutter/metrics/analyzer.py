#!/usr/bin/env python3
"""
シャッターメトリクス分析モジュール

メトリクスDBの生データからダッシュボード表示用の統計・チャートデータを生成します。
Flask 依存を持たない純粋なデータ変換ロジックのみを提供します。
"""

from __future__ import annotations

import datetime
import typing

if typing.TYPE_CHECKING:
    import rasp_shutter.metrics.collector

# 見合わせイベントの集計対象期間（日）
POSTPONE_RECENT_DAYS = 30

# センサーサンプルの表示対象期間（日）
SENSOR_SAMPLE_DISPLAY_DAYS = 7

# 見合わせ詳細テーブルの最大表示件数
POSTPONE_TABLE_LIMIT = 100

# what-if 分析で試す閾値スケール係数
WHAT_IF_SCALE_FACTORS = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5)

POSTPONE_REASON_LABEL = {
    "sensor_invalid": "センサー値不明",
    "too_dark": "暗くて見合わせ",
    "control_failure": "制御失敗",
}

# センサーサンプルの context 種別（NULL・未知の値は "unknown" に分類）
SENSOR_SAMPLE_CONTEXTS = ("auto_open_window", "auto_close_window", "off_hours")


class ShutterBreakdownEntry(typing.TypedDict):
    """シャッター個体別の操作・失敗集計（F-8）"""

    shutter_index: int | None
    shutter_name: str | None
    manual_open: int
    manual_close: int
    auto_open: int
    auto_close: int
    operation_total: int
    failure_total: int


def calculate_data_period(operation_metrics: list[dict]) -> dict:
    """データ期間を計算"""
    if not operation_metrics:
        return {"total_days": 0, "start_date": None, "end_date": None, "display_text": "データなし"}

    # 日付のみを抽出（str型のみをフィルタリング）
    dates: list[str] = [
        str(date) for op in operation_metrics if (date := op.get("date")) and isinstance(date, str)
    ]

    if not dates:
        return {"total_days": 0, "start_date": None, "end_date": None, "display_text": "データなし"}

    # 最古と最新の日付を取得
    start_date: str = min(dates)
    end_date: str = max(dates)

    # 日数を計算
    start_dt = datetime.datetime.fromisoformat(start_date)
    end_dt = datetime.datetime.fromisoformat(end_date)
    total_days = (end_dt - start_dt).days + 1

    # 表示テキストを生成
    if total_days == 1:
        display_text = f"過去1日間（{start_date.replace('-', '年', 1).replace('-', '月', 1)}日）"
    else:
        start_display = start_date.replace("-", "年", 1).replace("-", "月", 1) + "日"
        display_text = f"過去{total_days}日間（{start_display}〜）"

    return {
        "total_days": total_days,
        "start_date": start_date,
        "end_date": end_date,
        "display_text": display_text,
    }


def _extract_time_data(day_data: dict, key: str) -> float | None:
    """時刻データを抽出して時間形式に変換"""
    if not day_data.get(key):
        return None
    try:
        dt = datetime.datetime.fromisoformat(day_data[key].replace("Z", "+00:00"))
        return dt.hour + dt.minute / 60.0
    except (ValueError, TypeError):
        return None


def _collect_sensor_data_by_type(operation_metrics: list[dict], operation_type: str) -> dict:
    """操作タイプ別にセンサーデータを収集"""
    sensor_data: dict[str, list[float]] = {
        "open_lux": [],
        "close_lux": [],
        "open_solar_rad": [],
        "close_solar_rad": [],
        "open_altitude": [],
        "close_altitude": [],
    }

    for op_data in operation_metrics:
        if op_data.get("operation_type") == operation_type:
            action = op_data.get("action")
            if action in ["open", "close"]:
                for sensor_type in ["lux", "solar_rad", "altitude"]:
                    if op_data.get(sensor_type) is not None:
                        sensor_data[f"{action}_{sensor_type}"].append(op_data[sensor_type])

    return sensor_data


def generate_statistics(operation_metrics: list[dict], failure_metrics: list[dict]) -> dict:
    """メトリクスデータから統計情報を生成"""
    if not operation_metrics:
        return {
            "total_days": 0,
            "open_times": [],
            "close_times": [],
            "auto_sensor_data": {
                "open_lux": [],
                "close_lux": [],
                "open_solar_rad": [],
                "close_solar_rad": [],
                "open_altitude": [],
                "close_altitude": [],
            },
            "manual_sensor_data": {
                "open_lux": [],
                "close_lux": [],
                "open_solar_rad": [],
                "close_solar_rad": [],
                "open_altitude": [],
                "close_altitude": [],
            },
            "manual_open_total": 0,
            "manual_close_total": 0,
            "auto_open_total": 0,
            "auto_close_total": 0,
            "failure_total": len(failure_metrics),
        }

    # 日付ごとの最後の操作時刻を取得（時刻分析用）
    daily_last_operations = {}
    for op_data in operation_metrics:
        date = op_data.get("date")
        action = op_data.get("action")
        timestamp = op_data.get("timestamp")

        if date and action and timestamp:
            key = f"{date}_{action}"
            # より新しい時刻で上書き（最後の操作時刻を保持）
            daily_last_operations[key] = timestamp

    # 時刻データを収集（最後の操作時刻のみ）
    open_times = []
    close_times = []

    for key, timestamp in daily_last_operations.items():
        if (
            key.endswith("_open")
            and (t := _extract_time_data({"timestamp": timestamp}, "timestamp")) is not None
        ):
            open_times.append(t)
        elif (
            key.endswith("_close")
            and (t := _extract_time_data({"timestamp": timestamp}, "timestamp")) is not None
        ):
            close_times.append(t)

    # センサーデータを操作タイプ別に収集（autoとscheduleを統合）
    auto_sensor_data = _collect_sensor_data_by_type(operation_metrics, "auto")
    schedule_sensor_data = _collect_sensor_data_by_type(operation_metrics, "schedule")
    for key in auto_sensor_data:
        auto_sensor_data[key].extend(schedule_sensor_data[key])
    manual_sensor_data = _collect_sensor_data_by_type(operation_metrics, "manual")

    # カウント系データを集計（1回のループで全統計を計算）
    manual_open_total = 0
    manual_close_total = 0
    auto_open_total = 0
    auto_close_total = 0
    for op in operation_metrics:
        op_type = op.get("operation_type")
        action = op.get("action")
        if op_type == "manual":
            if action == "open":
                manual_open_total += 1
            elif action == "close":
                manual_close_total += 1
        elif op_type in ["auto", "schedule"]:
            if action == "open":
                auto_open_total += 1
            elif action == "close":
                auto_close_total += 1

    # 日数を計算
    unique_dates = {op.get("date") for op in operation_metrics if op.get("date")}

    return {
        "total_days": len(unique_dates),
        "open_times": open_times,
        "close_times": close_times,
        "auto_sensor_data": auto_sensor_data,
        "manual_sensor_data": manual_sensor_data,
        "manual_open_total": manual_open_total,
        "manual_close_total": manual_close_total,
        "auto_open_total": auto_open_total,
        "auto_close_total": auto_close_total,
        "failure_total": len(failure_metrics),
    }


def generate_postpone_statistics(postpone_events: list[dict]) -> dict:
    """見合わせイベントの集計"""
    total = len(postpone_events)
    open_count = sum(1 for ev in postpone_events if ev["intended_action"] == "open")
    close_count = total - open_count
    resolved_count = sum(1 for ev in postpone_events if ev.get("resolved_at"))

    reason_counts: dict[str, int] = {}
    trigger_counts: dict[str, int] = {}
    for ev in postpone_events:
        reason_counts[ev["reason"]] = reason_counts.get(ev["reason"], 0) + 1
        trigger_counts[ev["trigger"]] = trigger_counts.get(ev["trigger"], 0) + 1

    # resolve までのラグ（分）
    lag_minutes: list[float] = []
    for ev in postpone_events:
        if ev.get("resolved_at") and ev.get("timestamp"):
            try:
                started = datetime.datetime.fromisoformat(ev["timestamp"])
                resolved = datetime.datetime.fromisoformat(ev["resolved_at"])
                lag_minutes.append((resolved - started).total_seconds() / 60.0)
            except (ValueError, TypeError):
                continue

    return {
        "total": total,
        "open_count": open_count,
        "close_count": close_count,
        "resolved_count": resolved_count,
        "unresolved_count": total - resolved_count,
        "resolve_rate": (resolved_count / total * 100.0) if total > 0 else 0.0,
        "reason_counts": reason_counts,
        "trigger_counts": trigger_counts,
        "lag_minutes": lag_minutes,
    }


def prepare_postpone_chart_data(postpone_events: list[dict]) -> dict:
    """見合わせイベントから Chart.js 用データを構築"""
    # 理由 × 方向のクロス集計
    reason_action_matrix: dict[str, dict[str, int]] = {}
    for ev in postpone_events:
        reason = ev["reason"]
        action = ev["intended_action"]
        reason_action_matrix.setdefault(reason, {"open": 0, "close": 0})
        reason_action_matrix[reason][action] += 1

    # 日別の発生件数
    daily_counts: dict[str, dict[str, int]] = {}
    for ev in postpone_events:
        date = ev["date"]
        action = ev["intended_action"]
        daily_counts.setdefault(date, {"open": 0, "close": 0})
        daily_counts[date][action] += 1

    daily_sorted = sorted(daily_counts.items())
    return {
        "reason_action_matrix": reason_action_matrix,
        "daily_labels": [d for d, _ in daily_sorted],
        "daily_open": [c["open"] for _, c in daily_sorted],
        "daily_close": [c["close"] for _, c in daily_sorted],
    }


def prepare_sensor_samples_data(sensor_samples: list[dict], current_schedule: dict | None) -> dict:
    """センサーサンプルから Chart.js 用データ（時刻別・context別の散布図 + 閾値線）を構築

    x はその日の 0 時からの分。context が NULL または未知の値のサンプルは
    "unknown" に分類する（F-9b）。
    """
    series: dict[str, dict[str, list[dict[str, float]]]] = {
        sensor: {context: [] for context in (*SENSOR_SAMPLE_CONTEXTS, "unknown")}
        for sensor in ("lux", "solar_rad", "altitude")
    }

    for sample in sensor_samples:
        timestamp_str = sample.get("timestamp")
        if timestamp_str is None:
            continue
        try:
            ts = datetime.datetime.fromisoformat(timestamp_str)
        except ValueError:
            continue
        minutes = ts.hour * 60 + ts.minute
        context = sample.get("context")
        context_key = context if context in SENSOR_SAMPLE_CONTEXTS else "unknown"
        for sensor in ("lux", "solar_rad", "altitude"):
            value = sample.get(sensor)
            if value is None:
                continue
            series[sensor][context_key].append({"x": minutes, "y": float(value)})

    thresholds: dict[str, dict[str, float | None]] = {
        "lux": {"open": None, "close": None},
        "solar_rad": {"open": None, "close": None},
        "altitude": {"open": None, "close": None},
    }
    if current_schedule is not None:
        for direction in ("open", "close"):
            entry = current_schedule.get(direction, {})
            for sensor in ("lux", "solar_rad", "altitude"):
                value = entry.get(sensor)
                if value is not None:
                    thresholds[sensor][direction] = float(value)

    return {
        "sample_count": len(sensor_samples),
        "thresholds": thresholds,
        "series": series,
    }


def prepare_threshold_margin_data(operation_metrics: list[dict], current_schedule: dict | None) -> dict:
    """操作時のセンサー値が現在の閾値からどれだけ離れているかを集計"""
    if current_schedule is None:
        return {"open": [], "close": [], "thresholds": None}

    open_threshold = current_schedule.get("open", {})
    close_threshold = current_schedule.get("close", {})

    def _margins(direction: str, threshold: dict) -> list[dict[str, float | None]]:
        # open の場合: lux - threshold_lux のような「閾値を上回ったマージン」を返す
        # close の場合: threshold_lux - lux のような「閾値を下回ったマージン」を返す
        results: list[dict[str, float | None]] = []
        for op in operation_metrics:
            if op.get("action") != direction or op.get("operation_type") == "manual":
                continue
            entry: dict[str, float | None] = {}
            for sensor in ("lux", "solar_rad", "altitude"):
                value = op.get(sensor)
                threshold_value = threshold.get(sensor)
                if value is None or threshold_value is None:
                    entry[sensor] = None
                else:
                    margin = float(value) - float(threshold_value)
                    if direction == "close":
                        margin = -margin
                    entry[sensor] = margin
            results.append(entry)
        return results

    return {
        "open": _margins("open", open_threshold),
        "close": _margins("close", close_threshold),
        "thresholds": {
            "open": {k: open_threshold.get(k) for k in ("lux", "solar_rad", "altitude")},
            "close": {k: close_threshold.get(k) for k in ("lux", "solar_rad", "altitude")},
        },
    }


def _extract_daily_last_operations(operation_metrics: list[dict]) -> dict:
    """日付ごとの最後の操作時刻とセンサーデータを取得"""
    daily_last_operations: dict[str, dict] = {}

    for op_data in operation_metrics:
        date = op_data.get("date")
        action = op_data.get("action")
        timestamp = op_data.get("timestamp")

        if date and action and timestamp:
            key = f"{date}_{action}"
            # より新しい時刻で上書き
            if key not in daily_last_operations or timestamp > daily_last_operations[key]["timestamp"]:
                daily_last_operations[key] = {
                    "timestamp": timestamp,
                    "lux": op_data.get("lux"),
                    "solar_rad": op_data.get("solar_rad"),
                    "altitude": op_data.get("altitude"),
                }

    return daily_last_operations


def _extract_daily_data(date: str, action: str, daily_last_operations: dict) -> tuple[float | None, ...]:
    """指定した日付と操作の時刻とセンサーデータを抽出"""
    key = f"{date}_{action}"
    time_val = None
    lux_val = None
    solar_rad_val = None
    altitude_val = None

    if key in daily_last_operations:
        try:
            dt = datetime.datetime.fromisoformat(
                daily_last_operations[key]["timestamp"].replace("Z", "+00:00")
            )
            time_val = dt.hour + dt.minute / 60.0
            lux_val = daily_last_operations[key]["lux"]
            solar_rad_val = daily_last_operations[key]["solar_rad"]
            altitude_val = daily_last_operations[key]["altitude"]
        except (ValueError, TypeError):
            pass

    return time_val, lux_val, solar_rad_val, altitude_val


def prepare_time_series_data(operation_metrics: list[dict]) -> dict:
    """時系列データを準備"""
    daily_last_operations = _extract_daily_last_operations(operation_metrics)

    # 日付リストを生成
    date_set: set[str] = {op["date"] for op in operation_metrics if op.get("date")}
    unique_dates = sorted(date_set)

    dates = []
    open_times = []
    close_times = []
    open_lux = []
    close_lux = []
    open_solar_rad = []
    close_solar_rad = []
    open_altitude = []
    close_altitude = []

    for date in unique_dates:
        dates.append(date)

        # その日の最後の開操作時刻とセンサーデータ
        open_time, open_lux_val, open_solar_rad_val, open_altitude_val = _extract_daily_data(
            date, "open", daily_last_operations
        )

        # その日の最後の閉操作時刻とセンサーデータ
        close_time, close_lux_val, close_solar_rad_val, close_altitude_val = _extract_daily_data(
            date, "close", daily_last_operations
        )

        open_times.append(open_time)
        close_times.append(close_time)
        open_lux.append(open_lux_val)
        close_lux.append(close_lux_val)
        open_solar_rad.append(open_solar_rad_val)
        close_solar_rad.append(close_solar_rad_val)
        open_altitude.append(open_altitude_val)
        close_altitude.append(close_altitude_val)

    return {
        "dates": dates,
        "open_times": open_times,
        "close_times": close_times,
        "open_lux": open_lux,
        "close_lux": close_lux,
        "open_solar_rad": open_solar_rad,
        "close_solar_rad": close_solar_rad,
        "open_altitude": open_altitude,
        "close_altitude": close_altitude,
    }


def generate_shutter_statistics(
    operation_counts: list[dict], failure_counts: list[dict]
) -> list[ShutterBreakdownEntry]:
    """シャッター個体別の操作・失敗統計を生成（F-8）

    schedule と auto の操作は auto_open / auto_close に合算する。
    shutter_index が NULL の行（記録前の過去データ）は末尾に配置し、
    shutter_name は None のまま返す（表示側で「(記録前)」とする）。
    """
    entries: dict[tuple[int | None, str | None], ShutterBreakdownEntry] = {}

    def _entry(shutter_index: int | None, shutter_name: str | None) -> ShutterBreakdownEntry:
        key = (shutter_index, shutter_name)
        if key not in entries:
            entries[key] = ShutterBreakdownEntry(
                shutter_index=shutter_index,
                shutter_name=shutter_name,
                manual_open=0,
                manual_close=0,
                auto_open=0,
                auto_close=0,
                operation_total=0,
                failure_total=0,
            )
        return entries[key]

    for row in operation_counts:
        entry = _entry(row.get("shutter_index"), row.get("shutter_name"))
        count = int(row.get("count", 0))
        operation_type = row.get("operation_type")
        action = row.get("action")
        if operation_type == "manual":
            if action == "open":
                entry["manual_open"] += count
            elif action == "close":
                entry["manual_close"] += count
        elif operation_type in ("auto", "schedule"):
            if action == "open":
                entry["auto_open"] += count
            elif action == "close":
                entry["auto_close"] += count
        entry["operation_total"] += count

    for row in failure_counts:
        entry = _entry(row.get("shutter_index"), row.get("shutter_name"))
        entry["failure_total"] += int(row.get("count", 0))

    def _sort_key(entry: ShutterBreakdownEntry) -> tuple[bool, int, str]:
        shutter_index = entry["shutter_index"]
        return (shutter_index is None, shutter_index or 0, entry["shutter_name"] or "")

    return sorted(entries.values(), key=_sort_key)


def prepare_failure_time_series(daily_failure_counts: list[dict]) -> dict:
    """日別の制御失敗件数から Chart.js 用データを構築（F-9）"""
    return {
        "dates": [row["date"] for row in daily_failure_counts],
        "counts": [row["count"] for row in daily_failure_counts],
    }


def _calc_lag_minutes(event: dict) -> float | None:
    """見合わせイベントの解消ラグ（分）を計算。未解消・不正値は None"""
    if not event.get("resolved_at") or not event.get("timestamp"):
        return None
    try:
        started = datetime.datetime.fromisoformat(event["timestamp"])
        resolved = datetime.datetime.fromisoformat(event["resolved_at"])
    except (ValueError, TypeError):
        return None
    return (resolved - started).total_seconds() / 60.0


def prepare_postpone_events_table(
    postpone_events: list[dict], limit: int = POSTPONE_TABLE_LIMIT
) -> list[dict]:
    """見合わせ詳細テーブル用データを構築（新しい順、最大 limit 件）"""
    events_sorted = sorted(postpone_events, key=lambda ev: ev.get("timestamp") or "", reverse=True)

    results: list[dict] = []
    for event in events_sorted[:limit]:
        entry = {
            key: event.get(key)
            for key in (
                "timestamp",
                "date",
                "intended_action",
                "trigger",
                "scheduled_time",
                "reason",
                "lux",
                "solar_rad",
                "altitude",
                "resolved_at",
            )
        }
        entry["lag_minutes"] = _calc_lag_minutes(event)
        results.append(entry)

    return results


def analyze_threshold_tuning(postpone_events: list[dict], current_schedule: dict | None) -> dict:
    """閾値チューニング支援データを生成（F-7）

    what-if 判定条件は scheduler.py の check_brightness() の open 判定
    （lux > 閾値 AND solar_rad > 閾値 AND altitude > 閾値 の AND 条件）と同じ。
    閾値はイベント保存時のスナップショット列（threshold_*）を使用する。
    """
    empty: dict = {
        "shortfall": {"lux": [], "solar_rad": []},
        "what_if": [],
        "resolve_lag_minutes": [],
    }
    if current_schedule is None:
        return empty

    too_dark_open_events = [
        ev for ev in postpone_events if ev.get("intended_action") == "open" and ev.get("reason") == "too_dark"
    ]

    # 閾値までの不足量の分布
    shortfall: dict[str, list[float]] = {"lux": [], "solar_rad": []}
    for event in too_dark_open_events:
        for sensor, threshold_key in (("lux", "threshold_lux"), ("solar_rad", "threshold_solar_rad")):
            value = event.get(sensor)
            threshold_value = event.get(threshold_key)
            if value is not None and threshold_value is not None:
                shortfall[sensor].append(float(threshold_value) - float(value))

    # 閾値を scale 倍に緩和した場合に即時開けられたイベント数
    what_if: list[dict] = []
    total_events = len(too_dark_open_events)
    for scale in WHAT_IF_SCALE_FACTORS:
        immediate_open_count = 0
        for event in too_dark_open_events:
            lux = event.get("lux")
            solar_rad = event.get("solar_rad")
            altitude = event.get("altitude")
            threshold_lux = event.get("threshold_lux")
            threshold_solar_rad = event.get("threshold_solar_rad")
            threshold_altitude = event.get("threshold_altitude")
            if (
                lux is None
                or solar_rad is None
                or altitude is None
                or threshold_lux is None
                or threshold_solar_rad is None
                or threshold_altitude is None
            ):
                continue
            # NOTE: check_brightness() の open 判定と同じ AND 条件（altitude はスケールしない）
            if (
                lux > threshold_lux * scale
                and solar_rad > threshold_solar_rad * scale
                and altitude > threshold_altitude
            ):
                immediate_open_count += 1
        what_if.append(
            {
                "scale": scale,
                "immediate_open_count": immediate_open_count,
                "total_events": total_events,
                "ratio": (immediate_open_count / total_events) if total_events > 0 else 0.0,
            }
        )

    # 解消までのラグ（分）
    resolve_lag_minutes: list[float] = []
    for event in postpone_events:
        if event.get("intended_action") != "open":
            continue
        lag = _calc_lag_minutes(event)
        if lag is not None:
            resolve_lag_minutes.append(lag)

    return {
        "shortfall": shortfall,
        "what_if": what_if,
        "resolve_lag_minutes": resolve_lag_minutes,
    }


def build_dashboard_data(
    collector: rasp_shutter.metrics.collector.MetricsCollector, current_schedule: dict | None
) -> dict:
    """/api/metrics/data 用のダッシュボードデータを構築する唯一の入口"""
    operation_metrics = collector.get_all_operation_metrics()
    failure_metrics = collector.get_all_failure_metrics()
    postpone_events = collector.get_recent_postpone_events(POSTPONE_RECENT_DAYS)
    sensor_samples = collector.get_recent_sensor_samples(SENSOR_SAMPLE_DISPLAY_DAYS)

    stats = generate_statistics(operation_metrics, failure_metrics)
    data_period = calculate_data_period(operation_metrics)

    failure_dates = [str(date) for row in failure_metrics if (date := row.get("date"))]
    if failure_dates:
        daily_failure_counts = collector.get_daily_failure_counts(min(failure_dates), max(failure_dates))
    else:
        daily_failure_counts = []

    current_thresholds = None
    if current_schedule is not None:
        current_thresholds = {
            direction: {
                sensor: current_schedule.get(direction, {}).get(sensor)
                for sensor in ("lux", "solar_rad", "altitude")
            }
            for direction in ("open", "close")
        }

    return {
        "data_period": data_period,
        "stats": {
            "manual_open_total": stats["manual_open_total"],
            "manual_close_total": stats["manual_close_total"],
            "auto_open_total": stats["auto_open_total"],
            "auto_close_total": stats["auto_close_total"],
            "failure_total": stats["failure_total"],
            "total_days": stats["total_days"],
        },
        "shutter_breakdown": generate_shutter_statistics(
            collector.get_shutter_operation_counts(), collector.get_shutter_failure_counts()
        ),
        "postpone": {
            "summary": generate_postpone_statistics(postpone_events),
            "chart": prepare_postpone_chart_data(postpone_events),
            "events": prepare_postpone_events_table(postpone_events),
        },
        "charts": {
            "open_times": stats["open_times"],
            "close_times": stats["close_times"],
            "auto_sensor_data": stats["auto_sensor_data"],
            "manual_sensor_data": stats["manual_sensor_data"],
            "time_series": prepare_time_series_data(operation_metrics),
            "failure_time_series": prepare_failure_time_series(daily_failure_counts),
            "sensor_samples": prepare_sensor_samples_data(sensor_samples, current_schedule),
            "threshold_margin": prepare_threshold_margin_data(operation_metrics, current_schedule),
        },
        "threshold_tuning": analyze_threshold_tuning(postpone_events, current_schedule),
        "reason_labels": POSTPONE_REASON_LABEL,
        "current_thresholds": current_thresholds,
    }
