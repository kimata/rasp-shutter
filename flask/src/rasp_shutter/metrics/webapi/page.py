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

import my_lib.webapp.config
import rasp_shutter.metrics.collector
from PIL import Image, ImageDraw

import flask

blueprint = flask.Blueprint("metrics", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)


@blueprint.route("/api/metrics", methods=["GET"])
def metrics_view():
    """メトリクスダッシュボードページを表示"""
    try:
        # 設定からメトリクスデータパスを取得
        config = flask.current_app.config["CONFIG"]
        metrics_data_path = config.get("metrics", {}).get("data")

        # メトリクス収集器を取得
        collector = rasp_shutter.metrics.collector.get_collector(metrics_data_path)

        # 最近30日間のデータを取得
        operation_metrics = collector.get_recent_operation_metrics(days=30)
        failure_metrics = collector.get_recent_failure_metrics(days=30)

        # 統計データを生成
        stats = generate_statistics(operation_metrics, failure_metrics)

        # HTMLを生成
        html_content = generate_metrics_html(stats, operation_metrics)

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
    return img.resize((size, size), Image.LANCZOS)


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
    sensor_data = {
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
        if key.endswith("_open"):
            if (t := _extract_time_data({"timestamp": timestamp}, "timestamp")) is not None:
                open_times.append(t)
        elif key.endswith("_close"):
            if (t := _extract_time_data({"timestamp": timestamp}, "timestamp")) is not None:
                close_times.append(t)

    # センサーデータを操作タイプ別に収集
    auto_sensor_data = _collect_sensor_data_by_type(operation_metrics, "auto")
    auto_sensor_data.update(_collect_sensor_data_by_type(operation_metrics, "schedule"))
    manual_sensor_data = _collect_sensor_data_by_type(operation_metrics, "manual")

    # カウント系データを集計
    manual_open_total = sum(
        1 for op in operation_metrics if op.get("operation_type") == "manual" and op.get("action") == "open"
    )
    manual_close_total = sum(
        1 for op in operation_metrics if op.get("operation_type") == "manual" and op.get("action") == "close"
    )
    auto_open_total = sum(
        1
        for op in operation_metrics
        if op.get("operation_type") in ["auto", "schedule"] and op.get("action") == "open"
    )
    auto_close_total = sum(
        1
        for op in operation_metrics
        if op.get("operation_type") in ["auto", "schedule"] and op.get("action") == "close"
    )

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


def generate_metrics_html(stats: dict, operation_metrics: list[dict]) -> str:
    """Bulma CSSを使用したメトリクスHTMLを生成"""
    # JavaScript用データを準備
    chart_data = {
        "open_times": stats["open_times"],
        "close_times": stats["close_times"],
        "auto_sensor_data": stats["auto_sensor_data"],
        "manual_sensor_data": stats["manual_sensor_data"],
        "time_series": prepare_time_series_data(operation_metrics),
    }

    chart_data_json = json.dumps(chart_data)

    # URL_PREFIXを取得してfaviconパスを構築
    favicon_path = f"{my_lib.webapp.config.URL_PREFIX}/favicon.ico"

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>シャッター メトリクス ダッシュボード</title>
    <link rel="icon" type="image/x-icon" href="{favicon_path}">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@sgratzl/chartjs-chart-boxplot"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .metrics-card {{ margin-bottom: 1rem; }}
        @media (max-width: 768px) {{
            .metrics-card {{ margin-bottom: 0.75rem; }}
        }}
        .stat-number {{ font-size: 2rem; font-weight: bold; }}
        .chart-container {{ position: relative; height: 350px; margin: 0.5rem 0; }}
        @media (max-width: 768px) {{
            .chart-container {{ height: 300px; margin: 0.25rem 0; }}
            .container.is-fluid {{ padding: 0.25rem !important; }}
            .section {{ padding: 0.5rem 0.25rem !important; }}
            .card {{ margin-bottom: 1rem !important; }}
            .columns {{ margin: 0 !important; }}
            .column {{ padding: 0.25rem !important; }}
        }}
        .japanese-font {{
            font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN",
                         "Noto Sans CJK JP", "Yu Gothic", sans-serif;
        }}
    </style>
</head>
<body class="japanese-font">
    <div class="container is-fluid" style="padding: 0.5rem;">
        <section class="section" style="padding: 1rem 0.5rem;">
            <div class="container" style="max-width: 100%; padding: 0;">
                <h1 class="title is-2 has-text-centered">
                    <span class="icon is-large"><i class="fas fa-chart-line"></i></span>
                    シャッター メトリクス ダッシュボード
                </h1>
                <p class="subtitle has-text-centered">過去30日間のシャッター操作統計</p>

                <!-- 基本統計 -->
                {generate_basic_stats_section(stats)}

                <!-- 時刻分析 -->
                {generate_time_analysis_section()}

                <!-- センサーデータ分析 -->
                {generate_sensor_analysis_section()}
            </div>
        </section>
    </div>

    <script>
        const chartData = {chart_data_json};

        // チャート生成
        generateTimeCharts();
        generateAutoSensorCharts();
        generateManualSensorCharts();

        {generate_chart_javascript()}
    </script>
</html>
    """


def prepare_time_series_data(operation_metrics: list[dict]) -> dict:
    """時系列データを準備"""
    # 日付ごとの最後の操作時刻を取得
    daily_last_operations = {}
    for op_data in operation_metrics:
        date = op_data.get("date")
        action = op_data.get("action")
        timestamp = op_data.get("timestamp")

        if date and action and timestamp:
            key = f"{date}_{action}"
            daily_last_operations[key] = timestamp

    # 日付リストを生成
    unique_dates = sorted({op.get("date") for op in operation_metrics if op.get("date")})

    dates = []
    open_times = []
    close_times = []

    for date in unique_dates:
        dates.append(date)

        # その日の最後の開操作時刻
        open_key = f"{date}_open"
        open_time = None
        if open_key in daily_last_operations:
            try:
                open_dt = datetime.datetime.fromisoformat(
                    daily_last_operations[open_key].replace("Z", "+00:00")
                )
                open_time = open_dt.hour + open_dt.minute / 60.0
            except (ValueError, TypeError):
                pass

        # その日の最後の閉操作時刻
        close_key = f"{date}_close"
        close_time = None
        if close_key in daily_last_operations:
            try:
                close_dt = datetime.datetime.fromisoformat(
                    daily_last_operations[close_key].replace("Z", "+00:00")
                )
                close_time = close_dt.hour + close_dt.minute / 60.0
            except (ValueError, TypeError):
                pass

        open_times.append(open_time)
        close_times.append(close_time)

    return {"dates": dates, "open_times": open_times, "close_times": close_times}


def generate_basic_stats_section(stats: dict) -> str:
    """基本統計セクションのHTML生成"""
    return f"""
    <div class="section">
        <h2 class="title is-4">
            <span class="icon"><i class="fas fa-chart-bar"></i></span>
            基本統計（過去30日間）
        </h2>

        <div class="columns">
            <div class="column">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">操作回数</p>
                    </div>
                    <div class="card-content">
                        <div class="columns is-multiline">
                            <div class="column is-quarter">
                                <div class="has-text-centered">
                                    <p class="heading">👆 手動開操作 ☀️</p>
                                    <p class="stat-number has-text-success">{stats["manual_open_total"]:,}</p>
                                </div>
                            </div>
                            <div class="column is-quarter">
                                <div class="has-text-centered">
                                    <p class="heading">👆 手動閉操作 🌙</p>
                                    <p class="stat-number has-text-info">{stats["manual_close_total"]:,}</p>
                                </div>
                            </div>
                            <div class="column is-quarter">
                                <div class="has-text-centered">
                                    <p class="heading">🤖 自動開操作 ☀️</p>
                                    <p class="stat-number has-text-success">{stats["auto_open_total"]:,}</p>
                                </div>
                            </div>
                            <div class="column is-quarter">
                                <div class="has-text-centered">
                                    <p class="heading">🤖 自動閉操作 🌙</p>
                                    <p class="stat-number has-text-info">{stats["auto_close_total"]:,}</p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">制御失敗</p>
                                    <p class="stat-number has-text-danger">{stats["failure_total"]:,}</p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">データ収集日数</p>
                                    <p class="stat-number has-text-primary">{stats["total_days"]:,}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_time_analysis_section() -> str:
    """時刻分析セクションのHTML生成"""
    return """
    <div class="section">
        <h2 class="title is-4"><span class="icon"><i class="fas fa-clock"></i></span> 時刻分析</h2>

        <div class="columns">
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">☀️ 開操作時刻の頻度分布</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="openTimeHistogramChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">🌙 閉操作時刻の頻度分布</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="closeTimeHistogramChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_sensor_analysis_section() -> str:
    """センサーデータ分析セクションのHTML生成"""
    return """
    <div class="section">
        <h2 class="title is-4">
            <span class="icon"><i class="fas fa-robot"></i></span> 🤖 センサーデータ分析（自動操作）
        </h2>

        <!-- 照度データ -->
        <div class="columns">
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">🤖 自動開操作時の照度データ ☀️</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="autoOpenLuxChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">🤖 自動閉操作時の照度データ 🌙</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="autoCloseLuxChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 日射データ -->
        <div class="columns">
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">🤖 自動開操作時の日射データ ☀️</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="autoOpenSolarRadChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">🤖 自動閉操作時の日射データ 🌙</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="autoCloseSolarRadChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 太陽高度データ -->
        <div class="columns">
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">🤖 自動開操作時の太陽高度データ ☀️</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="autoOpenAltitudeChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">🤖 自動閉操作時の太陽高度データ 🌙</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="autoCloseAltitudeChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="section">
        <h2 class="title is-4">
            <span class="icon"><i class="fas fa-hand-paper"></i></span> 👆 センサーデータ分析（手動操作）
        </h2>

        <!-- 照度データ -->
        <div class="columns">
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">👆 手動開操作時の照度データ ☀️</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="manualOpenLuxChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">👆 手動閉操作時の照度データ 🌙</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="manualCloseLuxChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 日射データ -->
        <div class="columns">
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">👆 手動開操作時の日射データ ☀️</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="manualOpenSolarRadChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">👆 手動閉操作時の日射データ 🌙</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="manualCloseSolarRadChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 太陽高度データ -->
        <div class="columns">
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">👆 手動開操作時の太陽高度データ ☀️</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="manualOpenAltitudeChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">👆 手動閉操作時の太陽高度データ 🌙</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="manualCloseAltitudeChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_chart_javascript() -> str:
    """チャート生成用JavaScriptを生成"""
    return """
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

        function generateAutoSensorCharts() {
            // ヒストグラム生成のヘルパー関数
            function createHistogram(data, bins) {
                const hist = Array(bins.length - 1).fill(0);
                data.forEach(value => {
                    for (let i = 0; i < bins.length - 1; i++) {
                        if (value >= bins[i] && value < bins[i + 1]) {
                            hist[i]++;
                            break;
                        }
                    }
                });
                return hist;
            }

            // 自動開操作時照度チャート
            const autoOpenLuxCtx = document.getElementById('autoOpenLuxChart');
            if (autoOpenLuxCtx && chartData.auto_sensor_data.open_lux.length > 0) {
                const minLux = Math.min(...chartData.auto_sensor_data.open_lux);
                const maxLux = Math.max(...chartData.auto_sensor_data.open_lux);
                const bins = Array.from({length: 21}, (_, i) => minLux + (maxLux - minLux) * i / 20);
                const hist = createHistogram(chartData.auto_sensor_data.open_lux, bins);
                const total = chartData.auto_sensor_data.open_lux.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(autoOpenLuxCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b)),
                        datasets: [{
                            label: '🤖☀️ 自動開操作時照度頻度',
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

            // 自動閉操作時照度チャート
            const autoCloseLuxCtx = document.getElementById('autoCloseLuxChart');
            if (autoCloseLuxCtx && chartData.auto_sensor_data.close_lux.length > 0) {
                const minLux = Math.min(...chartData.auto_sensor_data.close_lux);
                const maxLux = Math.max(...chartData.auto_sensor_data.close_lux);
                const bins = Array.from({length: 21}, (_, i) => minLux + (maxLux - minLux) * i / 20);
                const hist = createHistogram(chartData.auto_sensor_data.close_lux, bins);
                const total = chartData.auto_sensor_data.close_lux.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(autoCloseLuxCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b)),
                        datasets: [{
                            label: '🤖🌙 自動閉操作時照度頻度',
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

            // 開操作時日射チャート
            const openSolarRadCtx = document.getElementById('openSolarRadChart');
            if (openSolarRadCtx && chartData.open_solar_rad.length > 0) {
                const minRad = Math.min(...chartData.open_solar_rad);
                const maxRad = Math.max(...chartData.open_solar_rad);
                const bins = Array.from({length: 21}, (_, i) => minRad + (maxRad - minRad) * i / 20);
                const hist = createHistogram(chartData.open_solar_rad, bins);
                const total = chartData.open_solar_rad.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(openSolarRadCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b)),
                        datasets: [{
                            label: '開操作時日射頻度',
                            data: histPercent,
                            backgroundColor: 'rgba(255, 159, 64, 0.7)',
                            borderColor: 'rgba(255, 159, 64, 1)',
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

            // 閉操作時日射チャート
            const closeSolarRadCtx = document.getElementById('closeSolarRadChart');
            if (closeSolarRadCtx && chartData.close_solar_rad.length > 0) {
                const minRad = Math.min(...chartData.close_solar_rad);
                const maxRad = Math.max(...chartData.close_solar_rad);
                const bins = Array.from({length: 21}, (_, i) => minRad + (maxRad - minRad) * i / 20);
                const hist = createHistogram(chartData.close_solar_rad, bins);
                const total = chartData.close_solar_rad.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(closeSolarRadCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b)),
                        datasets: [{
                            label: '閉操作時日射頻度',
                            data: histPercent,
                            backgroundColor: 'rgba(75, 192, 192, 0.7)',
                            borderColor: 'rgba(75, 192, 192, 1)',
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

            // 開操作時太陽高度チャート
            const openAltitudeCtx = document.getElementById('openAltitudeChart');
            if (openAltitudeCtx && chartData.open_altitude.length > 0) {
                const minAlt = Math.min(...chartData.open_altitude);
                const maxAlt = Math.max(...chartData.open_altitude);
                const bins = Array.from({length: 21}, (_, i) => minAlt + (maxAlt - minAlt) * i / 20);
                const hist = createHistogram(chartData.open_altitude, bins);
                const total = chartData.open_altitude.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(openAltitudeCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b * 10) / 10),
                        datasets: [{
                            label: '開操作時太陽高度頻度',
                            data: histPercent,
                            backgroundColor: 'rgba(255, 99, 132, 0.7)',
                            borderColor: 'rgba(255, 99, 132, 1)',
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

            // 閉操作時太陽高度チャート
            const closeAltitudeCtx = document.getElementById('closeAltitudeChart');
            if (closeAltitudeCtx && chartData.close_altitude.length > 0) {
                const minAlt = Math.min(...chartData.close_altitude);
                const maxAlt = Math.max(...chartData.close_altitude);
                const bins = Array.from({length: 21}, (_, i) => minAlt + (maxAlt - minAlt) * i / 20);
                const hist = createHistogram(chartData.close_altitude, bins);
                const total = chartData.close_altitude.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(closeAltitudeCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b * 10) / 10),
                        datasets: [{
                            label: '閉操作時太陽高度頻度',
                            data: histPercent,
                            backgroundColor: 'rgba(54, 162, 235, 0.7)',
                            borderColor: 'rgba(54, 162, 235, 1)',
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

        function generateManualSensorCharts() {
            // ヒストグラム生成のヘルパー関数
            function createHistogram(data, bins) {
                const hist = Array(bins.length - 1).fill(0);
                data.forEach(value => {
                    for (let i = 0; i < bins.length - 1; i++) {
                        if (value >= bins[i] && value < bins[i + 1]) {
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
                        labels: bins.slice(0, -1).map(b => Math.round(b)),
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
                        labels: bins.slice(0, -1).map(b => Math.round(b)),
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
                        labels: bins.slice(0, -1).map(b => Math.round(b)),
                        datasets: [{
                            label: '👆☀️ 手動開操作時日射頻度',
                            data: histPercent,
                            backgroundColor: 'rgba(255, 159, 64, 0.7)',
                            borderColor: 'rgba(255, 159, 64, 1)',
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
                        labels: bins.slice(0, -1).map(b => Math.round(b)),
                        datasets: [{
                            label: '👆🌙 手動閉操作時日射頻度',
                            data: histPercent,
                            backgroundColor: 'rgba(75, 192, 192, 0.7)',
                            borderColor: 'rgba(75, 192, 192, 1)',
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
                            backgroundColor: 'rgba(255, 99, 132, 0.7)',
                            borderColor: 'rgba(255, 99, 132, 1)',
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
                            backgroundColor: 'rgba(54, 162, 235, 0.7)',
                            borderColor: 'rgba(54, 162, 235, 1)',
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
    """
