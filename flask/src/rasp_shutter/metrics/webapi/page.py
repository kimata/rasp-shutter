#!/usr/bin/env python3
"""
シャッターメトリクス表示ページ

シャッター操作の統計情報とグラフを表示するWebページを提供します。
"""

from __future__ import annotations

import datetime
import json
import logging

import my_lib.webapp.config
import rasp_shutter.metrics.collector

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
        recent_metrics = collector.get_recent_metrics(days=30)

        # 統計データを生成
        stats = generate_statistics(recent_metrics)

        # HTMLを生成
        html_content = generate_metrics_html(stats, recent_metrics)

        return flask.Response(html_content, mimetype="text/html")

    except Exception as e:
        logging.exception("メトリクス表示の生成エラー")
        return flask.Response(f"エラー: {e!s}", mimetype="text/plain", status=500)


def _extract_time_data(day_data: dict, key: str) -> float | None:
    """時刻データを抽出して時間形式に変換"""
    if not day_data.get(key):
        return None
    try:
        dt = datetime.datetime.fromisoformat(day_data[key].replace("Z", "+00:00"))
        return dt.hour + dt.minute / 60.0
    except (ValueError, TypeError):
        return None


def _collect_sensor_data(metrics_data: list[dict]) -> dict:
    """センサーデータを収集"""
    sensor_data = {
        "open_lux": [],
        "close_lux": [],
        "open_solar_rad": [],
        "close_solar_rad": [],
        "open_altitude": [],
        "close_altitude": [],
    }

    for day_data in metrics_data:
        for sensor_type in ["lux", "solar_rad", "altitude"]:
            for operation in ["open", "close"]:
                key = f"last_{operation}_{sensor_type}"
                if day_data.get(key) is not None:
                    sensor_data[f"{operation}_{sensor_type}"].append(day_data[key])

    return sensor_data


def generate_statistics(metrics_data: list[dict]) -> dict:
    """メトリクスデータから統計情報を生成"""
    if not metrics_data:
        return {
            "total_days": 0,
            "open_times": [],
            "close_times": [],
            "open_lux": [],
            "close_lux": [],
            "open_solar_rad": [],
            "close_solar_rad": [],
            "open_altitude": [],
            "close_altitude": [],
            "manual_open_total": 0,
            "manual_close_total": 0,
            "failure_total": 0,
        }

    # 時刻データを収集
    open_times = [
        t for day_data in metrics_data if (t := _extract_time_data(day_data, "last_open_time")) is not None
    ]
    close_times = [
        t for day_data in metrics_data if (t := _extract_time_data(day_data, "last_close_time")) is not None
    ]

    # センサーデータを収集
    sensor_data = _collect_sensor_data(metrics_data)

    # カウント系データを累計
    manual_open_total = sum(day_data.get("manual_open_count", 0) for day_data in metrics_data)
    manual_close_total = sum(day_data.get("manual_close_count", 0) for day_data in metrics_data)
    failure_total = sum(day_data.get("failure_count", 0) for day_data in metrics_data)

    return {
        "total_days": len(metrics_data),
        "open_times": open_times,
        "close_times": close_times,
        **sensor_data,
        "manual_open_total": manual_open_total,
        "manual_close_total": manual_close_total,
        "failure_total": failure_total,
    }


def generate_metrics_html(stats: dict, raw_metrics: list[dict]) -> str:
    """Bulma CSSを使用したメトリクスHTMLを生成"""
    # JavaScript用データを準備
    chart_data = {
        "open_times": stats["open_times"],
        "close_times": stats["close_times"],
        "open_lux": stats["open_lux"],
        "close_lux": stats["close_lux"],
        "open_solar_rad": stats["open_solar_rad"],
        "close_solar_rad": stats["close_solar_rad"],
        "open_altitude": stats["open_altitude"],
        "close_altitude": stats["close_altitude"],
        "time_series": prepare_time_series_data(raw_metrics),
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
        .metrics-card {{ margin-bottom: 1.5rem; }}
        .stat-number {{ font-size: 2rem; font-weight: bold; }}
        .chart-container {{ position: relative; height: 400px; margin: 1rem 0; }}
        .japanese-font {{
            font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN",
                         "Noto Sans CJK JP", "Yu Gothic", sans-serif;
        }}
    </style>
</head>
<body class="japanese-font">
    <div class="container is-fluid">
        <section class="section">
            <div class="container">
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
        generateSensorCharts();

        {generate_chart_javascript()}
    </script>
</html>
    """


def prepare_time_series_data(raw_metrics: list[dict]) -> dict:
    """時系列データを準備"""
    dates = []
    open_times = []
    close_times = []

    for day_data in raw_metrics:
        date = day_data.get("date")
        if not date:
            continue

        dates.append(date)

        # 開閉時刻を時間として記録
        open_time = None
        close_time = None

        if day_data.get("last_open_time"):
            try:
                open_dt = datetime.datetime.fromisoformat(day_data["last_open_time"].replace("Z", "+00:00"))
                open_time = open_dt.hour + open_dt.minute / 60.0
            except (ValueError, TypeError):
                pass

        if day_data.get("last_close_time"):
            try:
                close_dt = datetime.datetime.fromisoformat(day_data["last_close_time"].replace("Z", "+00:00"))
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
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">手動開操作</p>
                                    <p class="stat-number has-text-success">{stats["manual_open_total"]:,}</p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">手動閉操作</p>
                                    <p class="stat-number has-text-info">{stats["manual_close_total"]:,}</p>
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
                        <p class="card-header-title">開操作時刻の頻度分布</p>
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
                        <p class="card-header-title">閉操作時刻の頻度分布</p>
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
        <h2 class="title is-4"><span class="icon"><i class="fas fa-sun"></i></span> センサーデータ分析</h2>

        <!-- 照度データ -->
        <div class="columns">
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">開操作時の照度データ</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="openLuxChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">閉操作時の照度データ</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="closeLuxChart"></canvas>
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
                        <p class="card-header-title">開操作時の日射データ</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="openSolarRadChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">閉操作時の日射データ</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="closeSolarRadChart"></canvas>
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
                        <p class="card-header-title">開操作時の太陽高度データ</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="openAltitudeChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">閉操作時の太陽高度データ</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="closeAltitudeChart"></canvas>
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
                            label: '開操作頻度',
                            data: openHistPercent,
                            backgroundColor: 'rgba(72, 199, 142, 0.7)',
                            borderColor: 'rgba(72, 199, 142, 1)',
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
                            label: '閉操作頻度',
                            data: closeHistPercent,
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
                                    text: '時刻'
                                }
                            }
                        }
                    }
                });
            }
        }

        function generateSensorCharts() {
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

            // 開操作時照度チャート
            const openLuxCtx = document.getElementById('openLuxChart');
            if (openLuxCtx && chartData.open_lux.length > 0) {
                const minLux = Math.min(...chartData.open_lux);
                const maxLux = Math.max(...chartData.open_lux);
                const bins = Array.from({length: 21}, (_, i) => minLux + (maxLux - minLux) * i / 20);
                const hist = createHistogram(chartData.open_lux, bins);
                const total = chartData.open_lux.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(openLuxCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b)),
                        datasets: [{
                            label: '開操作時照度頻度',
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

            // 閉操作時照度チャート
            const closeLuxCtx = document.getElementById('closeLuxChart');
            if (closeLuxCtx && chartData.close_lux.length > 0) {
                const minLux = Math.min(...chartData.close_lux);
                const maxLux = Math.max(...chartData.close_lux);
                const bins = Array.from({length: 21}, (_, i) => minLux + (maxLux - minLux) * i / 20);
                const hist = createHistogram(chartData.close_lux, bins);
                const total = chartData.close_lux.length;
                const histPercent = hist.map(count => total > 0 ? (count / total) * 100 : 0);

                new Chart(closeLuxCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.slice(0, -1).map(b => Math.round(b)),
                        datasets: [{
                            label: '閉操作時照度頻度',
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
    """
