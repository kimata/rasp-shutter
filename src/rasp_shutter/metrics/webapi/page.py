#!/usr/bin/env python3
"""
シャッターメトリクス表示ページ

シャッター操作の統計情報とグラフを表示するWebページを提供します。
"""

from __future__ import annotations

import datetime
import io
import json
import logging

import flask
from PIL import Image, ImageDraw

import rasp_shutter.config
import rasp_shutter.control.scheduler
import rasp_shutter.metrics.collector

blueprint = flask.Blueprint("metrics", __name__)


@blueprint.route("/api/metrics", methods=["GET"])
def metrics_view():
    """メトリクスダッシュボードページを表示"""
    try:
        # 設定からメトリクスデータパスを取得
        config = flask.current_app.config["CONFIG"]
        db_path = config.metrics.data
        if not db_path.exists():
            return flask.Response(
                f"<html><body><h1>メトリクスデータベースが見つかりません</h1>"
                f"<p>データベースファイル: {db_path}</p>"
                f"<p>システムが十分に動作してからメトリクスが生成されます。</p></body></html>",
                mimetype="text/html",
                status=503,
            )

        # メトリクス収集器を取得
        collector = rasp_shutter.metrics.collector.get_collector(db_path)

        # 全期間のデータを取得
        operation_metrics = collector.get_all_operation_metrics()
        failure_metrics = collector.get_all_failure_metrics()
        postpone_events = collector.get_recent_postpone_events(30)
        sensor_samples = collector.get_recent_sensor_samples(7)

        # 統計データを生成
        stats = generate_statistics(operation_metrics, failure_metrics)
        postpone_stats = generate_postpone_statistics(postpone_events)

        # データ期間を計算
        data_period = calculate_data_period(operation_metrics)

        # 現時点の閾値（schedule.dat から）を取得（取得失敗時は None）
        try:
            current_schedule = rasp_shutter.control.scheduler.schedule_load()
        except Exception:
            logging.warning("Failed to load current schedule for threshold reference", exc_info=True)
            current_schedule = None

        # HTMLを生成
        html_content = generate_metrics_html(
            stats,
            operation_metrics,
            data_period,
            postpone_events,
            postpone_stats,
            sensor_samples,
            current_schedule,
        )

        return flask.Response(html_content, mimetype="text/html")

    except Exception as e:
        logging.exception("メトリクス表示の生成エラー")
        return flask.Response(f"エラー: {e!s}", mimetype="text/plain", status=500)


@blueprint.route("/favicon.ico", methods=["GET"])
def favicon():
    """動的生成されたシャッターメトリクス用favicon.icoを返す"""
    try:
        # シャッターメトリクスアイコンを生成
        img = generate_shutter_metrics_icon()

        # ICO形式で出力
        output = io.BytesIO()
        img.save(output, format="ICO", sizes=[(32, 32)])
        output.seek(0)

        return flask.Response(
            output.getvalue(),
            mimetype="image/x-icon",
            headers={
                "Cache-Control": "public, max-age=3600",  # 1時間キャッシュ
                "Content-Type": "image/x-icon",
            },
        )
    except Exception:
        logging.exception("favicon生成エラー")
        return flask.Response("", status=500)


def generate_shutter_metrics_icon():
    """シャッターメトリクス用のアイコンを動的生成（アンチエイリアス対応）"""
    # アンチエイリアスのため4倍サイズで描画してから縮小
    scale = 4
    size = 32
    large_size = size * scale

    # 大きなサイズで描画
    img = Image.new("RGBA", (large_size, large_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 背景円（メトリクスらしい青色）
    margin = 2 * scale
    draw.ellipse(
        [margin, margin, large_size - margin, large_size - margin],
        fill=(52, 152, 219, 255),
        outline=(41, 128, 185, 255),
        width=2 * scale,
    )

    # グラフっぽい線を描画（座標を4倍に拡大）
    points = [
        (8 * scale, 20 * scale),
        (12 * scale, 16 * scale),
        (16 * scale, 12 * scale),
        (20 * scale, 14 * scale),
        (24 * scale, 10 * scale),
    ]

    # 折れ線グラフ
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=(255, 255, 255, 255), width=2 * scale)

    # データポイント
    point_size = 1 * scale
    for point in points:
        draw.ellipse(
            [point[0] - point_size, point[1] - point_size, point[0] + point_size, point[1] + point_size],
            fill=(255, 255, 255, 255),
        )

    # 32x32に縮小してアンチエイリアス効果を得る
    return img.resize((size, size), Image.Resampling.LANCZOS)


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
    """センサーサンプルから Chart.js 用データ（時刻別の散布図 + 閾値線）を構築"""

    # 各サンプルを (時刻HH:MM分換算, 値) のペアに展開
    def _points(key: str) -> list[dict[str, float]]:
        points: list[dict[str, float]] = []
        for sample in sensor_samples:
            value = sample.get(key)
            timestamp_str = sample.get("timestamp")
            if value is None or timestamp_str is None:
                continue
            try:
                ts = datetime.datetime.fromisoformat(timestamp_str)
            except ValueError:
                continue
            minutes = ts.hour * 60 + ts.minute
            points.append({"x": minutes, "y": float(value)})
        return points

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
        "lux_points": _points("lux"),
        "solar_rad_points": _points("solar_rad"),
        "altitude_points": _points("altitude"),
        "thresholds": thresholds,
        "sample_count": len(sensor_samples),
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


def generate_metrics_html(
    stats: dict,
    operation_metrics: list[dict],
    data_period: dict,
    postpone_events: list[dict] | None = None,
    postpone_stats: dict | None = None,
    sensor_samples: list[dict] | None = None,
    current_schedule: dict | None = None,
) -> str:
    """Tailwind CSSを使用したメトリクスHTMLを生成"""
    postpone_events = postpone_events or []
    postpone_stats = postpone_stats or {
        "total": 0,
        "open_count": 0,
        "close_count": 0,
        "resolved_count": 0,
        "unresolved_count": 0,
        "resolve_rate": 0.0,
        "reason_counts": {},
        "trigger_counts": {},
        "lag_minutes": [],
    }
    sensor_samples = sensor_samples or []

    # JavaScript用データを準備
    chart_data = {
        "open_times": stats["open_times"],
        "close_times": stats["close_times"],
        "auto_sensor_data": stats["auto_sensor_data"],
        "manual_sensor_data": stats["manual_sensor_data"],
        "time_series": prepare_time_series_data(operation_metrics),
        "postpone": prepare_postpone_chart_data(postpone_events),
        "sensor_samples": prepare_sensor_samples_data(sensor_samples, current_schedule),
        "threshold_margin": prepare_threshold_margin_data(operation_metrics, current_schedule),
    }

    chart_data_json = json.dumps(chart_data)

    # URL_PREFIXを取得してfaviconパスを構築
    favicon_path = f"{rasp_shutter.config.URL_PREFIX}/favicon.ico"

    return f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>シャッター メトリクス ダッシュボード</title>
    <link rel="icon" type="image/x-icon" href="{favicon_path}">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@sgratzl/chartjs-chart-boxplot"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .chart-container {{ position: relative; height: 350px; margin: 0.5rem 0; }}
        @media (max-width: 768px) {{
            .chart-container {{ height: 300px; margin: 0.25rem 0; }}
        }}
        .permalink-header {{ position: relative; display: inline-block; }}
        .permalink-icon {{
            opacity: 0;
            transition: opacity 0.2s;
            cursor: pointer;
            margin-left: 0.5rem;
            color: #3b82f6;
            font-size: 0.875rem;
        }}
        .permalink-icon:hover {{ color: #1d4ed8; }}
        .permalink-header:hover .permalink-icon {{ opacity: 1; }}
    </style>
</head>
<body class="bg-gray-50 font-sans">
    <div class="container mx-auto px-2 sm:px-4 py-4">
        <div class="text-center mb-8">
            <h1 class="text-2xl sm:text-3xl font-bold text-gray-800 mb-2">
                <i class="fas fa-chart-line mr-2 text-blue-600"></i>
                シャッター メトリクス ダッシュボード
            </h1>
            <p class="text-gray-600">{data_period["display_text"]}のシャッター操作統計</p>
        </div>

        <!-- 基本統計 -->
        {generate_basic_stats_section(stats)}

        <!-- 見合わせ分析 -->
        {generate_postpone_summary_section(postpone_stats)}

        <!-- 見合わせ詳細 -->
        {generate_postpone_detail_section(postpone_events)}

        <!-- 閾値マージン分析 -->
        {generate_threshold_margin_section(current_schedule)}

        <!-- センサー日内推移 -->
        {generate_sensor_profile_section(len(sensor_samples))}

        <!-- 時刻分析 -->
        {generate_time_analysis_section()}

        <!-- 時系列データ分析 -->
        {generate_time_series_section()}

        <!-- センサーデータ分析 -->
        {generate_sensor_analysis_section()}
    </div>

    <script>
        const chartData = {chart_data_json};

        // チャート生成
        generateTimeCharts();
        generateTimeSeriesCharts();
        generateAutoSensorCharts();
        generateManualSensorCharts();
        generatePostponeCharts();
        generateSensorProfileCharts();
        generateThresholdMarginCharts();

        // パーマリンク機能を初期化
        initializePermalinks();

        {generate_chart_javascript()}
    </script>
</html>
    """


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


def generate_basic_stats_section(stats: dict) -> str:
    """基本統計セクションのHTML生成"""
    return f"""
    <div class="mb-8">
        <h2 class="text-xl font-bold text-gray-800 mb-4 permalink-header" id="basic-stats">
            <i class="fas fa-chart-bar mr-2 text-blue-600"></i>
            基本統計
            <span class="permalink-icon " onclick="copyPermalink('basic-stats')">
                <i class="fas fa-link text-sm"></i>
            </span>
        </h2>

        <div class="bg-white rounded-lg shadow">
            <div class="border-b px-4 py-3">
                <p class="font-semibold text-gray-700">操作回数</p>
            </div>
            <div class="p-4">
                <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                    <div class="text-center">
                        <p class="text-xs uppercase tracking-wide text-gray-500 mb-1">👆 手動開操作 ☀️</p>
                        <p class="text-2xl font-bold text-green-500">{stats["manual_open_total"]:,}</p>
                    </div>
                    <div class="text-center">
                        <p class="text-xs uppercase tracking-wide text-gray-500 mb-1">👆 手動閉操作 🌙</p>
                        <p class="text-2xl font-bold text-blue-500">{stats["manual_close_total"]:,}</p>
                    </div>
                    <div class="text-center">
                        <p class="text-xs uppercase tracking-wide text-gray-500 mb-1">🤖 自動開操作 ☀️</p>
                        <p class="text-2xl font-bold text-green-500">{stats["auto_open_total"]:,}</p>
                    </div>
                    <div class="text-center">
                        <p class="text-xs uppercase tracking-wide text-gray-500 mb-1">🤖 自動閉操作 🌙</p>
                        <p class="text-2xl font-bold text-blue-500">{stats["auto_close_total"]:,}</p>
                    </div>
                    <div class="text-center">
                        <p class="text-xs uppercase tracking-wide text-gray-500 mb-1">制御失敗</p>
                        <p class="text-2xl font-bold text-red-500">{stats["failure_total"]:,}</p>
                    </div>
                    <div class="text-center">
                        <p class="text-xs uppercase tracking-wide text-gray-500 mb-1">データ収集日数</p>
                        <p class="text-2xl font-bold text-indigo-500">{stats["total_days"]:,}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


POSTPONE_REASON_LABEL = {
    "sensor_invalid": "センサー値不明",
    "too_dark": "暗くて見合わせ",
}


def _format_postpone_reason(reason: str) -> str:
    return POSTPONE_REASON_LABEL.get(reason, reason)


def generate_postpone_summary_section(postpone_stats: dict) -> str:
    """見合わせサマリーセクション (直近30日)"""
    return f"""
    <div class="mb-8">
        <h2 class="text-xl font-bold text-gray-800 mb-4 permalink-header" id="postpone-summary">
            <i class="fas fa-pause-circle mr-2 text-amber-600"></i>
            見合わせ分析 (直近30日)
            <span class="permalink-icon" onclick="copyPermalink('postpone-summary')">
                <i class="fas fa-link text-sm"></i>
            </span>
        </h2>

        <div class="bg-white rounded-lg shadow mb-4">
            <div class="border-b px-4 py-3">
                <p class="font-semibold text-gray-700">サマリー</p>
            </div>
            <div class="p-4">
                <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                    <div class="text-center">
                        <p class="text-xs uppercase tracking-wide text-gray-500 mb-1">見合わせ件数</p>
                        <p class="text-2xl font-bold text-amber-600">{postpone_stats["total"]:,}</p>
                    </div>
                    <div class="text-center">
                        <p class="text-xs uppercase tracking-wide text-gray-500 mb-1">☀️ 開け側</p>
                        <p class="text-2xl font-bold text-amber-500">{postpone_stats["open_count"]:,}</p>
                    </div>
                    <div class="text-center">
                        <p class="text-xs uppercase tracking-wide text-gray-500 mb-1">🌙 閉め側</p>
                        <p class="text-2xl font-bold text-amber-500">{postpone_stats["close_count"]:,}</p>
                    </div>
                    <div class="text-center">
                        <p class="text-xs uppercase tracking-wide text-gray-500 mb-1">解消済み</p>
                        <p class="text-2xl font-bold text-green-600">{postpone_stats["resolved_count"]:,}</p>
                    </div>
                    <div class="text-center">
                        <p class="text-xs uppercase tracking-wide text-gray-500 mb-1">解消率</p>
                        <p class="text-2xl font-bold text-green-600">{postpone_stats["resolve_rate"]:.1f}%</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3">
                    <p class="font-semibold text-gray-700">理由 × 方向</p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="postponeReasonChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3">
                    <p class="font-semibold text-gray-700">日別の発生件数</p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="postponeDailyChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_postpone_detail_section(postpone_events: list[dict]) -> str:
    """見合わせ詳細表 (新しい順、最大100件)"""
    if not postpone_events:
        rows_html = (
            '<tr><td colspan="8" class="text-center text-gray-500 py-4">'
            "直近30日の見合わせ記録はありません。"
            "</td></tr>"
        )
    else:
        rows: list[str] = []
        for ev in sorted(postpone_events, key=lambda e: e["timestamp"], reverse=True)[:100]:
            ts = ev.get("timestamp", "")
            try:
                display_ts = datetime.datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                display_ts = ts
            scheduled = ev.get("scheduled_time")
            scheduled_display = "-"
            if scheduled:
                try:
                    scheduled_display = datetime.datetime.fromisoformat(scheduled).strftime("%H:%M")
                except (ValueError, TypeError):
                    scheduled_display = scheduled
            action_label = "☀️ 開け" if ev["intended_action"] == "open" else "🌙 閉め"
            trigger_label = "スケジュール" if ev["trigger"] == "schedule" else "自動"
            reason_label = _format_postpone_reason(ev["reason"])
            resolved = ev.get("resolved_at")
            resolved_label = "未解消"
            resolved_class = "text-amber-600"
            if resolved:
                try:
                    started = datetime.datetime.fromisoformat(ts)
                    resolved_dt = datetime.datetime.fromisoformat(resolved)
                    lag_min = (resolved_dt - started).total_seconds() / 60.0
                    resolved_label = f"{lag_min:.0f} 分後 ({resolved_dt.strftime('%H:%M')})"
                    resolved_class = "text-green-600"
                except (ValueError, TypeError):
                    resolved_label = "解消済み"
                    resolved_class = "text-green-600"
            lux = ev.get("lux")
            solar_rad = ev.get("solar_rad")
            altitude = ev.get("altitude")

            def _fmt(value):
                return f"{value:.1f}" if isinstance(value, (int | float)) else "-"

            sensor_html = f"lux: {_fmt(lux)} / solar: {_fmt(solar_rad)} / alt: {_fmt(altitude)}"
            rows.append(
                f"<tr class='border-b'>"
                f"<td class='px-2 py-2 text-sm whitespace-nowrap'>{display_ts}</td>"
                f"<td class='px-2 py-2 text-sm'>{action_label}</td>"
                f"<td class='px-2 py-2 text-sm'>{trigger_label}</td>"
                f"<td class='px-2 py-2 text-sm whitespace-nowrap'>{scheduled_display}</td>"
                f"<td class='px-2 py-2 text-sm'>{reason_label}</td>"
                f"<td class='px-2 py-2 text-xs text-gray-600 whitespace-nowrap'>{sensor_html}</td>"
                f"<td class='px-2 py-2 text-sm {resolved_class} whitespace-nowrap'>{resolved_label}</td>"
                f"</tr>"
            )
        rows_html = "".join(rows)

    return f"""
    <div class="mb-8">
        <h2 class="text-xl font-bold text-gray-800 mb-4 permalink-header" id="postpone-detail">
            <i class="fas fa-list mr-2 text-amber-600"></i>
            見合わせ詳細 (最新100件)
            <span class="permalink-icon" onclick="copyPermalink('postpone-detail')">
                <i class="fas fa-link text-sm"></i>
            </span>
        </h2>
        <div class="bg-white rounded-lg shadow overflow-x-auto">
            <table class="min-w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-2 py-2 text-left text-xs font-semibold text-gray-700">発生日時</th>
                        <th class="px-2 py-2 text-left text-xs font-semibold text-gray-700">方向</th>
                        <th class="px-2 py-2 text-left text-xs font-semibold text-gray-700">トリガー</th>
                        <th class="px-2 py-2 text-left text-xs font-semibold text-gray-700">予定時刻</th>
                        <th class="px-2 py-2 text-left text-xs font-semibold text-gray-700">理由</th>
                        <th class="px-2 py-2 text-left text-xs font-semibold text-gray-700">センサー値</th>
                        <th class="px-2 py-2 text-left text-xs font-semibold text-gray-700">解消</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </div>
    """


def generate_threshold_margin_section(current_schedule: dict | None) -> str:
    """閾値マージン分析セクション"""
    threshold_text = "-"
    if current_schedule is not None:
        try:
            open_t = current_schedule.get("open", {})
            close_t = current_schedule.get("close", {})
            open_text = (
                f"開け閾値: lux≥{open_t.get('lux', '-')}, "
                f"solar_rad≥{open_t.get('solar_rad', '-')}, "
                f"alt≥{open_t.get('altitude', '-')}"
            )
            close_text = (
                f"閉め閾値: lux<{close_t.get('lux', '-')}, "
                f"solar_rad<{close_t.get('solar_rad', '-')}, "
                f"alt<{close_t.get('altitude', '-')}"
            )
            threshold_text = f"{open_text} ／ {close_text}"
        except Exception:
            threshold_text = "-"

    return f"""
    <div class="mb-8">
        <h2 class="text-xl font-bold text-gray-800 mb-4 permalink-header" id="threshold-margin">
            <i class="fas fa-sliders mr-2 text-blue-600"></i>
            閾値マージン分析
            <span class="permalink-icon" onclick="copyPermalink('threshold-margin')">
                <i class="fas fa-link text-sm"></i>
            </span>
        </h2>
        <div class="text-xs text-gray-500 mb-2">参照閾値: {threshold_text}</div>
        <div class="text-xs text-gray-500 mb-3">
            操作時のセンサー値が現在の閾値からどれだけ離れていたか。
            値が 0 に近いほどギリギリ。負の値は閾値を満たさないまま操作された記録（手動を除く）。
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3">
                    <p class="font-semibold text-gray-700">照度 (lux) のマージン</p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="thresholdMarginLuxChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3">
                    <p class="font-semibold text-gray-700">日射 (solar_rad) のマージン</p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="thresholdMarginSolarChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3">
                    <p class="font-semibold text-gray-700">太陽高度 (altitude) のマージン</p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="thresholdMarginAltitudeChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_sensor_profile_section(sample_count: int) -> str:
    """センサーサンプル日内推移セクション"""
    return f"""
    <div class="mb-8">
        <h2 class="text-xl font-bold text-gray-800 mb-4 permalink-header" id="sensor-profile">
            <i class="fas fa-wave-square mr-2 text-emerald-600"></i>
            センサー日内推移 (直近7日)
            <span class="permalink-icon" onclick="copyPermalink('sensor-profile')">
                <i class="fas fa-link text-sm"></i>
            </span>
        </h2>
        <div class="text-xs text-gray-500 mb-3">
            1分間隔のサンプル ({sample_count:,} 件) を時刻別に散布表示。赤線=開け閾値、青線=閉め閾値。
        </div>
        <div class="space-y-4">
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3">
                    <p class="font-semibold text-gray-700">💡 照度 (lux)</p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="sensorProfileLuxChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3">
                    <p class="font-semibold text-gray-700">☀️ 日射 (solar_rad)</p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="sensorProfileSolarChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3">
                    <p class="font-semibold text-gray-700">📐 太陽高度 (altitude)</p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="sensorProfileAltitudeChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_time_analysis_section() -> str:
    """時刻分析セクションのHTML生成"""
    return """
    <div class="mb-8">
        <h2 class="text-xl font-bold text-gray-800 mb-4 permalink-header" id="time-analysis">
            <i class="fas fa-clock mr-2 text-blue-600"></i>
            時刻分析
            <span class="permalink-icon " onclick="copyPermalink('time-analysis')">
                <i class="fas fa-link text-sm"></i>
            </span>
        </h2>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="open-time-histogram">
                    <p class="font-semibold text-gray-700">
                        ☀️ 開操作時刻の頻度分布
                        <span class="permalink-icon " onclick="copyPermalink('open-time-histogram')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="openTimeHistogramChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="close-time-histogram">
                    <p class="font-semibold text-gray-700">
                        🌙 閉操作時刻の頻度分布
                        <span class="permalink-icon " onclick="copyPermalink('close-time-histogram')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="closeTimeHistogramChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_time_series_section() -> str:
    """時系列データ分析セクションのHTML生成"""
    return """
    <div class="mb-8">
        <h2 class="text-xl font-bold text-gray-800 mb-4 permalink-header" id="time-series">
            <i class="fas fa-chart-line mr-2 text-blue-600"></i>
            時系列データ分析
            <span class="permalink-icon " onclick="copyPermalink('time-series')">
                <i class="fas fa-link text-sm"></i>
            </span>
        </h2>

        <div class="space-y-4">
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="time-series-chart">
                    <p class="font-semibold text-gray-700">
                        🕐 操作時刻の時系列遷移
                        <span class="permalink-icon " onclick="copyPermalink('time-series-chart')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="timeSeriesChart"></canvas>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="lux-time-series">
                    <p class="font-semibold text-gray-700">
                        💡 照度データの時系列遷移
                        <span class="permalink-icon " onclick="copyPermalink('lux-time-series')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="luxTimeSeriesChart"></canvas>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="solar-rad-time-series">
                    <p class="font-semibold text-gray-700">
                        ☀️ 日射データの時系列遷移
                        <span class="permalink-icon " onclick="copyPermalink('solar-rad-time-series')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="solarRadTimeSeriesChart"></canvas>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="altitude-time-series">
                    <p class="font-semibold text-gray-700">
                        📐 太陽高度の時系列遷移
                        <span class="permalink-icon " onclick="copyPermalink('altitude-time-series')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="altitudeTimeSeriesChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_sensor_analysis_section() -> str:
    """センサーデータ分析セクションのHTML生成"""
    return """
    <div class="mb-8">
        <h2 class="text-xl font-bold text-gray-800 mb-4 permalink-header" id="auto-sensor-analysis">
            <i class="fas fa-robot mr-2 text-blue-600"></i>
            センサーデータ分析（自動操作）
            <span class="permalink-icon " onclick="copyPermalink('auto-sensor-analysis')">
                <i class="fas fa-link text-sm"></i>
            </span>
        </h2>

        <!-- 照度データ -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="auto-open-lux">
                    <p class="font-semibold text-gray-700">
                        🤖 自動開操作時の照度データ ☀️
                        <span class="permalink-icon " onclick="copyPermalink('auto-open-lux')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="autoOpenLuxChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="auto-close-lux">
                    <p class="font-semibold text-gray-700">
                        🤖 自動閉操作時の照度データ 🌙
                        <span class="permalink-icon " onclick="copyPermalink('auto-close-lux')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="autoCloseLuxChart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- 日射データ -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="auto-open-solar-rad">
                    <p class="font-semibold text-gray-700">
                        🤖 自動開操作時の日射データ ☀️
                        <span class="permalink-icon " onclick="copyPermalink('auto-open-solar-rad')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="autoOpenSolarRadChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="auto-close-solar-rad">
                    <p class="font-semibold text-gray-700">
                        🤖 自動閉操作時の日射データ 🌙
                        <span class="permalink-icon " onclick="copyPermalink('auto-close-solar-rad')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="autoCloseSolarRadChart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- 太陽高度データ -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="auto-open-altitude">
                    <p class="font-semibold text-gray-700">
                        🤖 自動開操作時の太陽高度データ ☀️
                        <span class="permalink-icon " onclick="copyPermalink('auto-open-altitude')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="autoOpenAltitudeChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="auto-close-altitude">
                    <p class="font-semibold text-gray-700">
                        🤖 自動閉操作時の太陽高度データ 🌙
                        <span class="permalink-icon " onclick="copyPermalink('auto-close-altitude')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="autoCloseAltitudeChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="mb-8">
        <h2 class="text-xl font-bold text-gray-800 mb-4 permalink-header" id="manual-sensor-analysis">
            <i class="fas fa-hand-paper mr-2 text-blue-600"></i>
            センサーデータ分析（手動操作）
            <span class="permalink-icon " onclick="copyPermalink('manual-sensor-analysis')">
                <i class="fas fa-link text-sm"></i>
            </span>
        </h2>

        <!-- データなし表示 -->
        <div id="manual-no-data" class="hidden bg-gray-50 rounded-lg p-8 text-center">
            <i class="fas fa-inbox text-4xl text-gray-400 mb-4"></i>
            <p class="text-gray-600">手動操作のデータがまだありません。</p>
            <p class="text-sm text-gray-500 mt-2">
                手動でシャッターを操作すると、ここにセンサーデータが表示されます。
            </p>
        </div>

        <!-- グラフ表示エリア -->
        <div id="manual-charts">
        <!-- 照度データ -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="manual-open-lux">
                    <p class="font-semibold text-gray-700">
                        👆 手動開操作時の照度データ ☀️
                        <span class="permalink-icon " onclick="copyPermalink('manual-open-lux')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="manualOpenLuxChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="manual-close-lux">
                    <p class="font-semibold text-gray-700">
                        👆 手動閉操作時の照度データ 🌙
                        <span class="permalink-icon " onclick="copyPermalink('manual-close-lux')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="manualCloseLuxChart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- 日射データ -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="manual-open-solar-rad">
                    <p class="font-semibold text-gray-700">
                        👆 手動開操作時の日射データ ☀️
                        <span class="permalink-icon " onclick="copyPermalink('manual-open-solar-rad')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="manualOpenSolarRadChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="manual-close-solar-rad">
                    <p class="font-semibold text-gray-700">
                        👆 手動閉操作時の日射データ 🌙
                        <span class="permalink-icon " onclick="copyPermalink('manual-close-solar-rad')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="manualCloseSolarRadChart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- 太陽高度データ -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="manual-open-altitude">
                    <p class="font-semibold text-gray-700">
                        👆 手動開操作時の太陽高度データ ☀️
                        <span class="permalink-icon " onclick="copyPermalink('manual-open-altitude')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="manualOpenAltitudeChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow">
                <div class="border-b px-4 py-3 permalink-header" id="manual-close-altitude">
                    <p class="font-semibold text-gray-700">
                        👆 手動閉操作時の太陽高度データ 🌙
                        <span class="permalink-icon " onclick="copyPermalink('manual-close-altitude')">
                            <i class="fas fa-link text-sm"></i>
                        </span>
                    </p>
                </div>
                <div class="p-4">
                    <div class="chart-container">
                        <canvas id="manualCloseAltitudeChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
        </div><!-- manual-charts -->
    </div>
    """


def generate_chart_javascript() -> str:
    """チャート生成用JavaScriptを生成"""
    return """
        // 凡例を正方形に設定
        Chart.defaults.plugins.legend.labels.boxWidth = 12;
        Chart.defaults.plugins.legend.labels.boxHeight = 12;

        function initializePermalinks() {
            // ページ読み込み時にハッシュがある場合はスクロール
            if (window.location.hash) {
                const element = document.querySelector(window.location.hash);
                if (element) {
                    setTimeout(() => {
                        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }, 500); // チャート描画完了を待つ
                }
            }
        }

        function copyPermalink(sectionId) {
            const url = window.location.origin + window.location.pathname + '#' + sectionId;

            // Clipboard APIを使用してURLをコピー
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(url).then(() => {
                    showCopyNotification();
                }).catch(err => {
                    console.error('Failed to copy: ', err);
                    fallbackCopyToClipboard(url);
                });
            } else {
                // フォールバック
                fallbackCopyToClipboard(url);
            }

            // URLにハッシュを設定（履歴には残さない）
            window.history.replaceState(null, null, '#' + sectionId);
        }

        function fallbackCopyToClipboard(text) {
            const textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.left = "-999999px";
            textArea.style.top = "-999999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();

            try {
                document.execCommand('copy');
                showCopyNotification();
            } catch (err) {
                console.error('Fallback: Failed to copy', err);
                // 最後の手段として、プロンプトでURLを表示
                prompt('URLをコピーしてください:', text);
            }

            document.body.removeChild(textArea);
        }

        function showCopyNotification() {
            // 通知要素を作成
            const notification = document.createElement('div');
            notification.textContent = 'パーマリンクをコピーしました！';
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #23d160;
                color: white;
                padding: 12px 20px;
                border-radius: 4px;
                z-index: 1000;
                font-size: 14px;
                font-weight: 500;
                box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                transition: opacity 0.3s ease-in-out;
            `;

            document.body.appendChild(notification);

            // 3秒後にフェードアウト
            setTimeout(() => {
                notification.style.opacity = '0';
                setTimeout(() => {
                    if (notification.parentNode) {
                        document.body.removeChild(notification);
                    }
                }, 300);
            }, 3000);
        }
        function generateTimeCharts() {
            // 開操作時刻ヒストグラム
            const openTimeHistogramCtx = document.getElementById('openTimeHistogramChart');
            if (openTimeHistogramCtx && chartData.open_times.length > 0) {
                const bins = Array.from({length: 24}, (_, i) => i);
                const openHist = Array(24).fill(0);

                chartData.open_times.forEach(time => {
                    const hour = Math.floor(time);
                    if (hour >= 0 && hour < 24) openHist[hour]++;
                });

                // 頻度を%に変換
                const total = chartData.open_times.length;
                const openHistPercent = openHist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(openTimeHistogramCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.map(h => h + ':00'),
                        datasets: [{
                            label: '☀️ 開操作頻度',
                            data: openHistPercent,
                            backgroundColor: 'rgba(255, 206, 84, 0.7)',
                            borderColor: 'rgba(255, 206, 84, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '時刻'
                                }
                            }
                        }
                    }
                });
            }

            // 閉操作時刻ヒストグラム
            const closeTimeHistogramCtx = document.getElementById('closeTimeHistogramChart');
            if (closeTimeHistogramCtx && chartData.close_times.length > 0) {
                const bins = Array.from({length: 24}, (_, i) => i);
                const closeHist = Array(24).fill(0);

                chartData.close_times.forEach(time => {
                    const hour = Math.floor(time);
                    if (hour >= 0 && hour < 24) closeHist[hour]++;
                });

                // 頻度を%に変換
                const total = chartData.close_times.length;
                const closeHistPercent = closeHist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(closeTimeHistogramCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.map(h => h + ':00'),
                        datasets: [{
                            label: '🌙 閉操作頻度',
                            data: closeHistPercent,
                            backgroundColor: 'rgba(153, 102, 255, 0.7)',
                            borderColor: 'rgba(153, 102, 255, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '時刻'
                                }
                            }
                        }
                    }
                });
            }
        }

        function generateTimeSeriesCharts() {
            // 操作時刻の時系列グラフ
            const timeSeriesCtx = document.getElementById('timeSeriesChart');
            if (timeSeriesCtx && chartData.time_series && chartData.time_series.dates.length > 0) {
                new Chart(timeSeriesCtx, {
                    type: 'line',
                    data: {
                        labels: chartData.time_series.dates,
                        datasets: [
                            {
                                label: '☀️ 開操作時刻',
                                data: chartData.time_series.open_times,
                                borderColor: 'rgba(255, 206, 84, 1)',
                                backgroundColor: 'rgba(255, 206, 84, 0.1)',
                                tension: 0.1,
                                spanGaps: true
                            },
                            {
                                label: '🌙 閉操作時刻',
                                data: chartData.time_series.close_times,
                                borderColor: 'rgba(153, 102, 255, 1)',
                                backgroundColor: 'rgba(153, 102, 255, 0.1)',
                                tension: 0.1,
                                spanGaps: true
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 24,
                                title: {
                                    display: true,
                                    text: '時刻'
                                },
                                ticks: {
                                    callback: function(value) {
                                        const hour = Math.floor(value);
                                        const minute = Math.round((value - hour) * 60);
                                        return hour + ':' + (minute < 10 ? '0' : '') + minute;
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '日付'
                                }
                            }
                        }
                    }
                });
            }

            // 照度の時系列グラフ
            const luxTimeSeriesCtx = document.getElementById('luxTimeSeriesChart');
            if (luxTimeSeriesCtx && chartData.time_series && chartData.time_series.dates.length > 0) {
                new Chart(luxTimeSeriesCtx, {
                    type: 'line',
                    data: {
                        labels: chartData.time_series.dates,
                        datasets: [
                            {
                                label: '☀️ 開操作時照度',
                                data: chartData.time_series.open_lux,
                                borderColor: 'rgba(255, 206, 84, 1)',
                                backgroundColor: 'rgba(255, 206, 84, 0.1)',
                                tension: 0.1,
                                spanGaps: true
                            },
                            {
                                label: '🌙 閉操作時照度',
                                data: chartData.time_series.close_lux,
                                borderColor: 'rgba(153, 102, 255, 1)',
                                backgroundColor: 'rgba(153, 102, 255, 0.1)',
                                tension: 0.1,
                                spanGaps: true
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: '照度（lux）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value.toLocaleString();
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '日付'
                                }
                            }
                        }
                    }
                });
            }

            // 日射の時系列グラフ
            const solarRadTimeSeriesCtx = document.getElementById('solarRadTimeSeriesChart');
            if (solarRadTimeSeriesCtx && chartData.time_series && chartData.time_series.dates.length > 0) {
                new Chart(solarRadTimeSeriesCtx, {
                    type: 'line',
                    data: {
                        labels: chartData.time_series.dates,
                        datasets: [
                            {
                                label: '☀️ 開操作時日射',
                                data: chartData.time_series.open_solar_rad,
                                borderColor: 'rgba(255, 206, 84, 1)',
                                backgroundColor: 'rgba(255, 206, 84, 0.1)',
                                tension: 0.1,
                                spanGaps: true
                            },
                            {
                                label: '🌙 閉操作時日射',
                                data: chartData.time_series.close_solar_rad,
                                borderColor: 'rgba(153, 102, 255, 1)',
                                backgroundColor: 'rgba(153, 102, 255, 0.1)',
                                tension: 0.1,
                                spanGaps: true
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: '日射（W/m²）'
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '日付'
                                }
                            }
                        }
                    }
                });
            }

            // 太陽高度の時系列グラフ
            const altitudeTimeSeriesCtx = document.getElementById('altitudeTimeSeriesChart');
            if (altitudeTimeSeriesCtx && chartData.time_series && chartData.time_series.dates.length > 0) {
                new Chart(altitudeTimeSeriesCtx, {
                    type: 'line',
                    data: {
                        labels: chartData.time_series.dates,
                        datasets: [
                            {
                                label: '☀️ 開操作時太陽高度',
                                data: chartData.time_series.open_altitude,
                                borderColor: 'rgba(255, 206, 84, 1)',
                                backgroundColor: 'rgba(255, 206, 84, 0.1)',
                                tension: 0.1,
                                spanGaps: true
                            },
                            {
                                label: '🌙 閉操作時太陽高度',
                                data: chartData.time_series.close_altitude,
                                borderColor: 'rgba(153, 102, 255, 1)',
                                backgroundColor: 'rgba(153, 102, 255, 0.1)',
                                tension: 0.1,
                                spanGaps: true
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false
                        },
                        scales: {
                            y: {
                                title: {
                                    display: true,
                                    text: '太陽高度（度）'
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '日付'
                                }
                            }
                        }
                    }
                });
            }
        }

        function generateAutoSensorCharts() {
            // ヒストグラム生成のヘルパー関数
            function createHistogram(data, bins) {
                const hist = Array(bins.length - 1).fill(0);
                data.forEach(value => {
                    for (let i = 0; i < bins.length - 1; i++) {
                        // 最後のビンは最大値も含める（<= を使用）
                        const isLastBin = (i === bins.length - 2);
                        if (value >= bins[i] && (isLastBin ? value <= bins[i + 1] : value < bins[i + 1])) {
                            hist[i]++;
                            break;
                        }
                    }
                });
                return hist;
            }

            // ヒストグラムパーセントを計算するヘルパー関数
            function calcHistPercent(data) {
                if (!data || data.length === 0) return { bins: [], histPercent: [], maxPercent: 0 };
                const minVal = Math.min(...data);
                const maxVal = Math.max(...data);
                const bins = Array.from({length: 21}, (_, i) => minVal + (maxVal - minVal) * i / 20);
                const hist = createHistogram(data, bins);
                const total = data.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);
                const maxPercent = Math.max(...histPercent);
                return { bins, histPercent, maxPercent };
            }

            // 各カテゴリの開/閉の最大頻度を事前計算
            const openLuxData = calcHistPercent(chartData.auto_sensor_data.open_lux);
            const closeLuxData = calcHistPercent(chartData.auto_sensor_data.close_lux);
            const luxMax = Math.max(openLuxData.maxPercent, closeLuxData.maxPercent, 10);
            const luxMaxY = Math.ceil(luxMax / 10) * 10;

            const openSolarRadData = calcHistPercent(chartData.auto_sensor_data.open_solar_rad);
            const closeSolarRadData = calcHistPercent(chartData.auto_sensor_data.close_solar_rad);
            const solarRadMax = Math.max(openSolarRadData.maxPercent, closeSolarRadData.maxPercent, 10);
            const solarRadMaxY = Math.ceil(solarRadMax / 10) * 10;

            const openAltitudeData = calcHistPercent(chartData.auto_sensor_data.open_altitude);
            const closeAltitudeData = calcHistPercent(chartData.auto_sensor_data.close_altitude);
            const altitudeMax = Math.max(openAltitudeData.maxPercent, closeAltitudeData.maxPercent, 10);
            const altitudeMaxY = Math.ceil(altitudeMax / 10) * 10;

            // 自動開操作時照度チャート
            const autoOpenLuxCtx = document.getElementById('autoOpenLuxChart');
            if (autoOpenLuxCtx && openLuxData.bins.length > 0) {
                new Chart(autoOpenLuxCtx, {
                    type: 'bar',
                    data: {
                        labels: openLuxData.bins.slice(0, -1).map(b => Math.round(b).toLocaleString()),
                        datasets: [{
                            label: '🤖☀️ 自動開操作時照度頻度',
                            data: openLuxData.histPercent,
                            backgroundColor: 'rgba(255, 206, 84, 0.7)',
                            borderColor: 'rgba(255, 206, 84, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: luxMaxY,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '照度（lux）'
                                }
                            }
                        }
                    }
                });
            }

            // 自動閉操作時照度チャート
            const autoCloseLuxCtx = document.getElementById('autoCloseLuxChart');
            if (autoCloseLuxCtx && closeLuxData.bins.length > 0) {
                new Chart(autoCloseLuxCtx, {
                    type: 'bar',
                    data: {
                        labels: closeLuxData.bins.slice(0, -1).map(b => Math.round(b).toLocaleString()),
                        datasets: [{
                            label: '🤖🌙 自動閉操作時照度頻度',
                            data: closeLuxData.histPercent,
                            backgroundColor: 'rgba(153, 102, 255, 0.7)',
                            borderColor: 'rgba(153, 102, 255, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: luxMaxY,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '照度（lux）'
                                }
                            }
                        }
                    }
                });
            }

            // 自動開操作時日射チャート
            const autoOpenSolarRadCtx = document.getElementById('autoOpenSolarRadChart');
            if (autoOpenSolarRadCtx && openSolarRadData.bins.length > 0) {
                new Chart(autoOpenSolarRadCtx, {
                    type: 'bar',
                    data: {
                        labels: openSolarRadData.bins.slice(0, -1).map(b => Math.round(b).toLocaleString()),
                        datasets: [{
                            label: '🤖☀️ 自動開操作時日射頻度',
                            data: openSolarRadData.histPercent,
                            backgroundColor: 'rgba(255, 206, 84, 0.7)',
                            borderColor: 'rgba(255, 206, 84, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: solarRadMaxY,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '日射（W/m²）'
                                }
                            }
                        }
                    }
                });
            }

            // 自動閉操作時日射チャート
            const autoCloseSolarRadCtx = document.getElementById('autoCloseSolarRadChart');
            if (autoCloseSolarRadCtx && closeSolarRadData.bins.length > 0) {
                new Chart(autoCloseSolarRadCtx, {
                    type: 'bar',
                    data: {
                        labels: closeSolarRadData.bins.slice(0, -1).map(b => Math.round(b).toLocaleString()),
                        datasets: [{
                            label: '🤖🌙 自動閉操作時日射頻度',
                            data: closeSolarRadData.histPercent,
                            backgroundColor: 'rgba(153, 102, 255, 0.7)',
                            borderColor: 'rgba(153, 102, 255, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: solarRadMaxY,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '日射（W/m²）'
                                }
                            }
                        }
                    }
                });
            }

            // 自動開操作時太陽高度チャート
            const autoOpenAltitudeCtx = document.getElementById('autoOpenAltitudeChart');
            if (autoOpenAltitudeCtx && openAltitudeData.bins.length > 0) {
                new Chart(autoOpenAltitudeCtx, {
                    type: 'bar',
                    data: {
                        labels: openAltitudeData.bins.slice(0, -1).map(b => Math.round(b * 10) / 10),
                        datasets: [{
                            label: '🤖☀️ 自動開操作時太陽高度頻度',
                            data: openAltitudeData.histPercent,
                            backgroundColor: 'rgba(255, 206, 84, 0.7)',
                            borderColor: 'rgba(255, 206, 84, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: altitudeMaxY,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '太陽高度（度）'
                                }
                            }
                        }
                    }
                });
            }

            // 自動閉操作時太陽高度チャート
            const autoCloseAltitudeCtx = document.getElementById('autoCloseAltitudeChart');
            if (autoCloseAltitudeCtx && closeAltitudeData.bins.length > 0) {
                new Chart(autoCloseAltitudeCtx, {
                    type: 'bar',
                    data: {
                        labels: closeAltitudeData.bins.slice(0, -1).map(b => Math.round(b * 10) / 10),
                        datasets: [{
                            label: '🤖🌙 自動閉操作時太陽高度頻度',
                            data: closeAltitudeData.histPercent,
                            backgroundColor: 'rgba(153, 102, 255, 0.7)',
                            borderColor: 'rgba(153, 102, 255, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: altitudeMaxY,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '太陽高度（度）'
                                }
                            }
                        }
                    }
                });
            }
        }

        function generateManualSensorCharts() {
            // 手動操作データの有無をチェック
            const manualData = chartData.manual_sensor_data;
            const hasManualData = manualData && (
                (manualData.open_lux && manualData.open_lux.length > 0) ||
                (manualData.close_lux && manualData.close_lux.length > 0) ||
                (manualData.open_solar_rad && manualData.open_solar_rad.length > 0) ||
                (manualData.close_solar_rad && manualData.close_solar_rad.length > 0) ||
                (manualData.open_altitude && manualData.open_altitude.length > 0) ||
                (manualData.close_altitude && manualData.close_altitude.length > 0)
            );

            const noDataDiv = document.getElementById('manual-no-data');
            const chartsDiv = document.getElementById('manual-charts');

            if (!hasManualData) {
                // データがない場合はメッセージを表示し、グラフを非表示
                if (noDataDiv) noDataDiv.classList.remove('hidden');
                if (chartsDiv) chartsDiv.classList.add('hidden');
                return;
            } else {
                // データがある場合はグラフを表示し、メッセージを非表示
                if (noDataDiv) noDataDiv.classList.add('hidden');
                if (chartsDiv) chartsDiv.classList.remove('hidden');
            }

            // ヒストグラム生成のヘルパー関数
            function createHistogram(data, bins) {
                const hist = Array(bins.length - 1).fill(0);
                data.forEach(value => {
                    for (let i = 0; i < bins.length - 1; i++) {
                        // 最後のビンは最大値も含める（<= を使用）
                        const isLastBin = (i === bins.length - 2);
                        if (value >= bins[i] && (isLastBin ? value <= bins[i + 1] : value < bins[i + 1])) {
                            hist[i]++;
                            break;
                        }
                    }
                });
                return hist;
            }

            // 手動開操作時照度チャート
            const manualOpenLuxCtx = document.getElementById('manualOpenLuxChart');
            if (manualOpenLuxCtx && chartData.manual_sensor_data &&
                chartData.manual_sensor_data.open_lux &&
                chartData.manual_sensor_data.open_lux.length > 0) {
                const minLux = Math.min(...chartData.manual_sensor_data.open_lux);
                const maxLux = Math.max(...chartData.manual_sensor_data.open_lux);
                const bins = Array.from({length: 21}, (_, i) => minLux + (maxLux - minLux) * i / 20);
                const hist = createHistogram(chartData.manual_sensor_data.open_lux, bins);
                const total = chartData.manual_sensor_data.open_lux.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(manualOpenLuxCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b).toLocaleString()),
                        datasets: [{
                            label: '👆☀️ 手動開操作時照度頻度',
                            data: histPercent,
                            backgroundColor: 'rgba(255, 206, 84, 0.7)',
                            borderColor: 'rgba(255, 206, 84, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '照度（lux）'
                                }
                            }
                        }
                    }
                });
            }

            // 手動閉操作時照度チャート
            const manualCloseLuxCtx = document.getElementById('manualCloseLuxChart');
            if (manualCloseLuxCtx && chartData.manual_sensor_data &&
                chartData.manual_sensor_data.close_lux &&
                chartData.manual_sensor_data.close_lux.length > 0) {
                const minLux = Math.min(...chartData.manual_sensor_data.close_lux);
                const maxLux = Math.max(...chartData.manual_sensor_data.close_lux);
                const bins = Array.from({length: 21}, (_, i) => minLux + (maxLux - minLux) * i / 20);
                const hist = createHistogram(chartData.manual_sensor_data.close_lux, bins);
                const total = chartData.manual_sensor_data.close_lux.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(manualCloseLuxCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b).toLocaleString()),
                        datasets: [{
                            label: '👆🌙 手動閉操作時照度頻度',
                            data: histPercent,
                            backgroundColor: 'rgba(153, 102, 255, 0.7)',
                            borderColor: 'rgba(153, 102, 255, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '照度（lux）'
                                }
                            }
                        }
                    }
                });
            }

            // 手動開操作時日射チャート
            const manualOpenSolarRadCtx = document.getElementById('manualOpenSolarRadChart');
            if (manualOpenSolarRadCtx && chartData.manual_sensor_data &&
                chartData.manual_sensor_data.open_solar_rad &&
                chartData.manual_sensor_data.open_solar_rad.length > 0) {
                const minRad = Math.min(...chartData.manual_sensor_data.open_solar_rad);
                const maxRad = Math.max(...chartData.manual_sensor_data.open_solar_rad);
                const bins = Array.from({length: 21}, (_, i) => minRad + (maxRad - minRad) * i / 20);
                const hist = createHistogram(chartData.manual_sensor_data.open_solar_rad, bins);
                const total = chartData.manual_sensor_data.open_solar_rad.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(manualOpenSolarRadCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b).toLocaleString()),
                        datasets: [{
                            label: '👆☀️ 手動開操作時日射頻度',
                            data: histPercent,
                            backgroundColor: 'rgba(255, 206, 84, 0.7)',
                            borderColor: 'rgba(255, 206, 84, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '日射（W/m²）'
                                }
                            }
                        }
                    }
                });
            }

            // 手動閉操作時日射チャート
            const manualCloseSolarRadCtx = document.getElementById('manualCloseSolarRadChart');
            if (manualCloseSolarRadCtx && chartData.manual_sensor_data &&
                chartData.manual_sensor_data.close_solar_rad &&
                chartData.manual_sensor_data.close_solar_rad.length > 0) {
                const minRad = Math.min(...chartData.manual_sensor_data.close_solar_rad);
                const maxRad = Math.max(...chartData.manual_sensor_data.close_solar_rad);
                const bins = Array.from({length: 21}, (_, i) => minRad + (maxRad - minRad) * i / 20);
                const hist = createHistogram(chartData.manual_sensor_data.close_solar_rad, bins);
                const total = chartData.manual_sensor_data.close_solar_rad.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(manualCloseSolarRadCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b).toLocaleString()),
                        datasets: [{
                            label: '👆🌙 手動閉操作時日射頻度',
                            data: histPercent,
                            backgroundColor: 'rgba(153, 102, 255, 0.7)',
                            borderColor: 'rgba(153, 102, 255, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '日射（W/m²）'
                                }
                            }
                        }
                    }
                });
            }

            // 手動開操作時太陽高度チャート
            const manualOpenAltitudeCtx = document.getElementById('manualOpenAltitudeChart');
            if (manualOpenAltitudeCtx && chartData.manual_sensor_data &&
                chartData.manual_sensor_data.open_altitude &&
                chartData.manual_sensor_data.open_altitude.length > 0) {
                const minAlt = Math.min(...chartData.manual_sensor_data.open_altitude);
                const maxAlt = Math.max(...chartData.manual_sensor_data.open_altitude);
                const bins = Array.from({length: 21}, (_, i) => minAlt + (maxAlt - minAlt) * i / 20);
                const hist = createHistogram(chartData.manual_sensor_data.open_altitude, bins);
                const total = chartData.manual_sensor_data.open_altitude.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(manualOpenAltitudeCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b * 10) / 10),
                        datasets: [{
                            label: '👆☀️ 手動開操作時太陽高度頻度',
                            data: histPercent,
                            backgroundColor: 'rgba(255, 206, 84, 0.7)',
                            borderColor: 'rgba(255, 206, 84, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '太陽高度（度）'
                                }
                            }
                        }
                    }
                });
            }

            // 手動閉操作時太陽高度チャート
            const manualCloseAltitudeCtx = document.getElementById('manualCloseAltitudeChart');
            if (manualCloseAltitudeCtx && chartData.manual_sensor_data &&
                chartData.manual_sensor_data.close_altitude &&
                chartData.manual_sensor_data.close_altitude.length > 0) {
                const minAlt = Math.min(...chartData.manual_sensor_data.close_altitude);
                const maxAlt = Math.max(...chartData.manual_sensor_data.close_altitude);
                const bins = Array.from({length: 21}, (_, i) => minAlt + (maxAlt - minAlt) * i / 20);
                const hist = createHistogram(chartData.manual_sensor_data.close_altitude, bins);
                const total = chartData.manual_sensor_data.close_altitude.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(manualCloseAltitudeCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b * 10) / 10),
                        datasets: [{
                            label: '👆🌙 手動閉操作時太陽高度頻度',
                            data: histPercent,
                            backgroundColor: 'rgba(153, 102, 255, 0.7)',
                            borderColor: 'rgba(153, 102, 255, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                title: {
                                    display: true,
                                    text: '頻度（%）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '太陽高度（度）'
                                }
                            }
                        }
                    }
                });
            }
        }

        function generatePostponeCharts() {
            const postpone = chartData.postpone || {};

            // 理由 × 方向 (積み上げ棒)
            const reasonCtx = document.getElementById('postponeReasonChart');
            if (reasonCtx) {
                const matrix = postpone.reason_action_matrix || {};
                const reasonLabelMap = {
                    'sensor_invalid': 'センサー値不明',
                    'too_dark': '暗くて見合わせ'
                };
                const reasons = Object.keys(matrix);
                const labels = reasons.map(r => reasonLabelMap[r] || r);
                const openData = reasons.map(r => matrix[r].open || 0);
                const closeData = reasons.map(r => matrix[r].close || 0);
                new Chart(reasonCtx, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: '☀️ 開け',
                                data: openData,
                                backgroundColor: 'rgba(251, 191, 36, 0.7)',
                                borderColor: 'rgba(251, 191, 36, 1)',
                                borderWidth: 1
                            },
                            {
                                label: '🌙 閉め',
                                data: closeData,
                                backgroundColor: 'rgba(59, 130, 246, 0.7)',
                                borderColor: 'rgba(59, 130, 246, 1)',
                                borderWidth: 1
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            x: { stacked: true },
                            y: {
                                stacked: true,
                                beginAtZero: true,
                                title: { display: true, text: '件数' }
                            }
                        }
                    }
                });
            }

            // 日別の発生件数
            const dailyCtx = document.getElementById('postponeDailyChart');
            if (dailyCtx) {
                new Chart(dailyCtx, {
                    type: 'bar',
                    data: {
                        labels: postpone.daily_labels || [],
                        datasets: [
                            {
                                label: '☀️ 開け',
                                data: postpone.daily_open || [],
                                backgroundColor: 'rgba(251, 191, 36, 0.7)'
                            },
                            {
                                label: '🌙 閉め',
                                data: postpone.daily_close || [],
                                backgroundColor: 'rgba(59, 130, 246, 0.7)'
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            x: { stacked: true },
                            y: { stacked: true, beginAtZero: true, title: { display: true, text: '件数' } }
                        }
                    }
                });
            }
        }

        function _minutesToHHMM(minutes) {
            const h = Math.floor(minutes / 60);
            const m = Math.floor(minutes % 60);
            return ('0' + h).slice(-2) + ':' + ('0' + m).slice(-2);
        }

        function _renderSensorProfile(canvasId, points, thresholds, yLabel) {
            const ctx = document.getElementById(canvasId);
            if (!ctx) return;
            const datasets = [
                {
                    label: 'センサー値',
                    data: points,
                    backgroundColor: 'rgba(16, 185, 129, 0.45)',
                    borderColor: 'rgba(16, 185, 129, 0.8)',
                    pointRadius: 1.5,
                    showLine: false
                }
            ];
            if (thresholds && thresholds.open !== null && thresholds.open !== undefined) {
                datasets.push({
                    type: 'line',
                    label: '開け閾値',
                    data: [
                        { x: 0, y: thresholds.open },
                        { x: 1440, y: thresholds.open }
                    ],
                    borderColor: 'rgba(220, 38, 38, 0.7)',
                    borderWidth: 2,
                    borderDash: [4, 4],
                    pointRadius: 0,
                    fill: false
                });
            }
            if (thresholds && thresholds.close !== null && thresholds.close !== undefined) {
                datasets.push({
                    type: 'line',
                    label: '閉め閾値',
                    data: [
                        { x: 0, y: thresholds.close },
                        { x: 1440, y: thresholds.close }
                    ],
                    borderColor: 'rgba(37, 99, 235, 0.7)',
                    borderWidth: 2,
                    borderDash: [4, 4],
                    pointRadius: 0,
                    fill: false
                });
            }
            new Chart(ctx, {
                type: 'scatter',
                data: { datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'linear',
                            min: 0,
                            max: 1440,
                            ticks: {
                                stepSize: 120,
                                callback: function(value) { return _minutesToHHMM(value); }
                            },
                            title: { display: true, text: '時刻' }
                        },
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: yLabel }
                        }
                    }
                }
            });
        }

        function generateSensorProfileCharts() {
            const data = chartData.sensor_samples || {};
            const thresholds = data.thresholds || {};
            _renderSensorProfile(
                'sensorProfileLuxChart',
                data.lux_points || [],
                thresholds.lux,
                '照度 (lux)'
            );
            _renderSensorProfile(
                'sensorProfileSolarChart',
                data.solar_rad_points || [],
                thresholds.solar_rad,
                '日射 (W/m²)'
            );
            _renderSensorProfile(
                'sensorProfileAltitudeChart',
                data.altitude_points || [],
                thresholds.altitude,
                '太陽高度 (°)'
            );
        }

        function _renderMargin(canvasId, sensor, xLabel) {
            const ctx = document.getElementById(canvasId);
            if (!ctx) return;
            const margin = chartData.threshold_margin || {};
            const openMargins = (margin.open || [])
                .map(e => e[sensor])
                .filter(v => v !== null && v !== undefined);
            const closeMargins = (margin.close || [])
                .map(e => e[sensor])
                .filter(v => v !== null && v !== undefined);
            if (openMargins.length === 0 && closeMargins.length === 0) {
                ctx.getContext('2d').fillText('データがありません', 20, 40);
                return;
            }

            const all = openMargins.concat(closeMargins);
            const minV = Math.min(...all, 0);
            const maxV = Math.max(...all, 0);
            const span = (maxV - minV) || 1;
            const binCount = 20;
            const bins = Array.from({length: binCount + 1}, (_, i) => minV + span * i / binCount);
            const labels = bins.slice(0, -1).map(b => b.toFixed(1));

            function histogram(values, edges) {
                const hist = new Array(edges.length - 1).fill(0);
                for (const v of values) {
                    for (let i = 0; i < edges.length - 1; i++) {
                        if (v >= edges[i] && (i === edges.length - 2 ? v <= edges[i+1] : v < edges[i+1])) {
                            hist[i]++;
                            break;
                        }
                    }
                }
                return hist;
            }

            const openHist = histogram(openMargins, bins);
            const closeHist = histogram(closeMargins, bins);

            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: '☀️ 開け操作',
                            data: openHist,
                            backgroundColor: 'rgba(251, 191, 36, 0.7)'
                        },
                        {
                            label: '🌙 閉め操作',
                            data: closeHist,
                            backgroundColor: 'rgba(59, 130, 246, 0.7)'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { title: { display: true, text: xLabel } },
                        y: { beginAtZero: true, title: { display: true, text: '件数' } }
                    }
                }
            });
        }

        function generateThresholdMarginCharts() {
            _renderMargin('thresholdMarginLuxChart', 'lux', 'lux マージン');
            _renderMargin('thresholdMarginSolarChart', 'solar_rad', 'solar_rad マージン (W/m²)');
            _renderMargin('thresholdMarginAltitudeChart', 'altitude', 'altitude マージン (°)');
        }
    """
