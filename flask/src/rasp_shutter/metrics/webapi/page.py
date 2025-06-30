#!/usr/bin/env python3
"""
シャッターメトリクス表示ページ

シャッター操作の統計情報とグラフを表示するWebページを提供します。
"""

import datetime
import json
import logging
import pathlib
from typing import Dict, List

import my_lib.webapp.config
import rasp_shutter.metrics.collector

import flask

blueprint = flask.Blueprint("metrics", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)


@blueprint.route("/api/metrics", methods=["GET"])
def metrics_view():
    """メトリクスダッシュボードページを表示"""
    try:
        # メトリクス収集器を取得
        collector = rasp_shutter.metrics.collector.get_collector()

        # 最近30日間のデータを取得
        recent_metrics = collector.get_recent_metrics(days=30)

        # 統計データを生成
        stats = generate_statistics(recent_metrics)

        # HTMLを生成
        html_content = generate_metrics_html(stats, recent_metrics)

        return flask.Response(html_content, mimetype="text/html")

    except Exception as e:
        logging.error(f"メトリクス表示の生成エラー: {e}")
        return flask.Response(f"エラー: {str(e)}", mimetype="text/plain", status=500)


def generate_statistics(metrics_data: List[Dict]) -> Dict:
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

    open_times = []
    close_times = []
    open_lux = []
    close_lux = []
    open_solar_rad = []
    close_solar_rad = []
    open_altitude = []
    close_altitude = []

    manual_open_total = 0
    manual_close_total = 0
    failure_total = 0

    for day_data in metrics_data:
        # 時刻データを収集（時間のみ）
        if day_data.get("last_open_time"):
            try:
                open_dt = datetime.datetime.fromisoformat(day_data["last_open_time"].replace("Z", "+00:00"))
                open_times.append(open_dt.hour + open_dt.minute / 60.0)
            except (ValueError, TypeError):
                pass

        if day_data.get("last_close_time"):
            try:
                close_dt = datetime.datetime.fromisoformat(day_data["last_close_time"].replace("Z", "+00:00"))
                close_times.append(close_dt.hour + close_dt.minute / 60.0)
            except (ValueError, TypeError):
                pass

        # センサーデータを収集
        if day_data.get("last_open_lux") is not None:
            open_lux.append(day_data["last_open_lux"])
        if day_data.get("last_close_lux") is not None:
            close_lux.append(day_data["last_close_lux"])
        if day_data.get("last_open_solar_rad") is not None:
            open_solar_rad.append(day_data["last_open_solar_rad"])
        if day_data.get("last_close_solar_rad") is not None:
            close_solar_rad.append(day_data["last_close_solar_rad"])
        if day_data.get("last_open_altitude") is not None:
            open_altitude.append(day_data["last_open_altitude"])
        if day_data.get("last_close_altitude") is not None:
            close_altitude.append(day_data["last_close_altitude"])

        # カウント系データを累計
        manual_open_total += day_data.get("manual_open_count", 0)
        manual_close_total += day_data.get("manual_close_count", 0)
        failure_total += day_data.get("failure_count", 0)

    return {
        "total_days": len(metrics_data),
        "open_times": open_times,
        "close_times": close_times,
        "open_lux": open_lux,
        "close_lux": close_lux,
        "open_solar_rad": open_solar_rad,
        "close_solar_rad": close_solar_rad,
        "open_altitude": open_altitude,
        "close_altitude": close_altitude,
        "manual_open_total": manual_open_total,
        "manual_close_total": manual_close_total,
        "failure_total": failure_total,
    }


def generate_metrics_html(stats: Dict, raw_metrics: List[Dict]) -> str:
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

    html = f"""
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
        .japanese-font {{ font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans CJK JP", "Yu Gothic", sans-serif; }}
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

    return html


def prepare_time_series_data(raw_metrics: List[Dict]) -> Dict:
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


def generate_basic_stats_section(stats: Dict) -> str:
    """基本統計セクションのHTML生成"""
    return f"""
    <div class="section">
        <h2 class="title is-4"><span class="icon"><i class="fas fa-chart-bar"></i></span> 基本統計（過去30日間）</h2>

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
                        <p class="card-header-title">開閉時刻の時系列遷移（箱ひげ図）</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="timeBoxplotChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">時刻別頻度分布</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="timeHistogramChart"></canvas>
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

        <div class="columns">
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">照度データ</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="luxChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">日射データ</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="solarRadChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="columns">
            <div class="column">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">太陽高度データ</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="altitudeChart"></canvas>
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
            // 箱ひげ図
            const timeBoxplotCtx = document.getElementById('timeBoxplotChart');
            if (timeBoxplotCtx && chartData.open_times.length > 0 && chartData.close_times.length > 0) {
                new Chart(timeBoxplotCtx, {
                    type: 'boxplot',
                    data: {
                        labels: ['開操作', '閉操作'],
                        datasets: [{
                            label: '時刻分布（時）',
                            data: [chartData.open_times, chartData.close_times],
                            backgroundColor: ['rgba(72, 199, 142, 0.5)', 'rgba(54, 162, 235, 0.5)'],
                            borderColor: ['rgba(72, 199, 142, 1)', 'rgba(54, 162, 235, 1)'],
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: false,
                                min: 0,
                                max: 24,
                                title: {
                                    display: true,
                                    text: '時刻（時）'
                                },
                                ticks: {
                                    callback: function(value) {
                                        const hour = Math.floor(value);
                                        const minute = Math.round((value - hour) * 60);
                                        return hour + ':' + (minute < 10 ? '0' : '') + minute;
                                    }
                                }
                            }
                        }
                    }
                });
            }

            // ヒストグラム
            const timeHistogramCtx = document.getElementById('timeHistogramChart');
            if (timeHistogramCtx) {
                const allTimes = [...chartData.open_times, ...chartData.close_times];
                const bins = Array.from({length: 24}, (_, i) => i);
                const openHist = Array(24).fill(0);
                const closeHist = Array(24).fill(0);

                chartData.open_times.forEach(time => {
                    const hour = Math.floor(time);
                    if (hour >= 0 && hour < 24) openHist[hour]++;
                });

                chartData.close_times.forEach(time => {
                    const hour = Math.floor(time);
                    if (hour >= 0 && hour < 24) closeHist[hour]++;
                });

                new Chart(timeHistogramCtx, {
                    type: 'bar',
                    data: {
                        labels: bins.map(h => h + ':00'),
                        datasets: [
                            {
                                label: '開操作',
                                data: openHist,
                                backgroundColor: 'rgba(72, 199, 142, 0.7)',
                                borderColor: 'rgba(72, 199, 142, 1)',
                                borderWidth: 1
                            },
                            {
                                label: '閉操作',
                                data: closeHist,
                                backgroundColor: 'rgba(54, 162, 235, 0.7)',
                                borderColor: 'rgba(54, 162, 235, 1)',
                                borderWidth: 1
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: '回数'
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
            // 照度チャート
            const luxCtx = document.getElementById('luxChart');
            if (luxCtx) {
                new Chart(luxCtx, {
                    type: 'scatter',
                    data: {
                        datasets: [
                            {
                                label: '開操作時の照度',
                                data: chartData.open_lux.map((lux, i) => ({x: i, y: lux})),
                                backgroundColor: 'rgba(255, 206, 84, 0.7)',
                                borderColor: 'rgba(255, 206, 84, 1)',
                                pointRadius: 4
                            },
                            {
                                label: '閉操作時の照度',
                                data: chartData.close_lux.map((lux, i) => ({x: i, y: lux})),
                                backgroundColor: 'rgba(153, 102, 255, 0.7)',
                                borderColor: 'rgba(153, 102, 255, 1)',
                                pointRadius: 4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                title: {
                                    display: true,
                                    text: '照度（lux）'
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: 'データ点'
                                }
                            }
                        }
                    }
                });
            }

            // 日射チャート
            const solarRadCtx = document.getElementById('solarRadChart');
            if (solarRadCtx) {
                new Chart(solarRadCtx, {
                    type: 'scatter',
                    data: {
                        datasets: [
                            {
                                label: '開操作時の日射',
                                data: chartData.open_solar_rad.map((rad, i) => ({x: i, y: rad})),
                                backgroundColor: 'rgba(255, 159, 64, 0.7)',
                                borderColor: 'rgba(255, 159, 64, 1)',
                                pointRadius: 4
                            },
                            {
                                label: '閉操作時の日射',
                                data: chartData.close_solar_rad.map((rad, i) => ({x: i, y: rad})),
                                backgroundColor: 'rgba(75, 192, 192, 0.7)',
                                borderColor: 'rgba(75, 192, 192, 1)',
                                pointRadius: 4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                title: {
                                    display: true,
                                    text: '日射（W/m²）'
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: 'データ点'
                                }
                            }
                        }
                    }
                });
            }

            // 太陽高度チャート
            const altitudeCtx = document.getElementById('altitudeChart');
            if (altitudeCtx) {
                new Chart(altitudeCtx, {
                    type: 'scatter',
                    data: {
                        datasets: [
                            {
                                label: '開操作時の太陽高度',
                                data: chartData.open_altitude.map((alt, i) => ({x: i, y: alt})),
                                backgroundColor: 'rgba(255, 99, 132, 0.7)',
                                borderColor: 'rgba(255, 99, 132, 1)',
                                pointRadius: 4
                            },
                            {
                                label: '閉操作時の太陽高度',
                                data: chartData.close_altitude.map((alt, i) => ({x: i, y: alt})),
                                backgroundColor: 'rgba(54, 162, 235, 0.7)',
                                borderColor: 'rgba(54, 162, 235, 1)',
                                pointRadius: 4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
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
                                    text: 'データ点'
                                }
                            }
                        }
                    }
                });
            }
        }
    """
