#!/usr/bin/env python3
"""
シャッターメトリクス表示ページ

シャッター操作の統計情報とグラフを表示するWebページと、
その表示用データを返す JSON API を提供します。
"""

from __future__ import annotations

import functools
import io
import logging
import pathlib
import sqlite3

import flask
import PIL.Image
import PIL.ImageDraw

import rasp_shutter.control.scheduler
import rasp_shutter.metrics.analyzer
import rasp_shutter.metrics.collector

# favicon のブラウザキャッシュ期間（秒）
FAVICON_CACHE_MAX_AGE_SEC = 3600

blueprint = flask.Blueprint(
    "metrics",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/metrics/static",
)


def _get_metrics_db_path() -> pathlib.Path:
    """設定からメトリクスデータベースのパスを取得"""
    config = flask.current_app.config["CONFIG"]
    return config.metrics.data


def _load_current_schedule() -> dict | None:
    """現時点の閾値参照用スケジュールを取得（取得失敗時は None）"""
    try:
        return rasp_shutter.control.scheduler.schedule_load()
    except (AssertionError, OSError, RuntimeError):
        logging.warning("Failed to load current schedule for threshold reference", exc_info=True)
        return None


@blueprint.route("/api/metrics", methods=["GET"])
def metrics_view():
    """メトリクスダッシュボードページを表示"""
    db_path = _get_metrics_db_path()
    if not db_path.exists():
        return flask.Response(
            f"<html><body><h1>メトリクスデータベースが見つかりません</h1>"
            f"<p>データベースファイル: {db_path}</p>"
            f"<p>システムが十分に動作してからメトリクスが生成されます。</p></body></html>",
            mimetype="text/html",
            status=503,
        )

    return flask.render_template(
        "metrics/dashboard.html",
        data_url=flask.url_for("metrics.metrics_data"),
        charts_js_url=flask.url_for("metrics.static", filename="js/metrics-charts.js"),
        dashboard_js_url=flask.url_for("metrics.static", filename="js/metrics-dashboard.js"),
        favicon_url=flask.url_for("metrics.favicon"),
    )


@blueprint.route("/api/metrics/data", methods=["GET"])
def metrics_data():
    """メトリクスダッシュボード用データを JSON で返す"""
    db_path = _get_metrics_db_path()
    if not db_path.exists():
        return flask.jsonify({"error": "メトリクスデータベースが見つかりません"}), 503

    try:
        collector = rasp_shutter.metrics.collector.get_collector(db_path)
        current_schedule = _load_current_schedule()
        return flask.jsonify(rasp_shutter.metrics.analyzer.build_dashboard_data(collector, current_schedule))
    except (sqlite3.Error, OSError) as e:
        logging.exception("メトリクスデータの生成エラー")
        return flask.jsonify({"error": str(e)}), 500


@blueprint.route("/favicon.ico", methods=["GET"])
def favicon():
    """動的生成されたシャッターメトリクス用favicon.icoを返す"""
    try:
        return flask.Response(
            _generate_favicon_ico(),
            mimetype="image/x-icon",
            headers={
                "Cache-Control": f"public, max-age={FAVICON_CACHE_MAX_AGE_SEC}",
                "Content-Type": "image/x-icon",
            },
        )
    except (OSError, ValueError):
        logging.exception("favicon生成エラー")
        return flask.Response("", status=500)


@functools.lru_cache(maxsize=1)
def _generate_favicon_ico() -> bytes:
    """favicon の ICO バイト列を生成（PIL による生成は初回のみ）"""
    img = generate_shutter_metrics_icon()
    output = io.BytesIO()
    img.save(output, format="ICO", sizes=[(32, 32)])
    return output.getvalue()


def generate_shutter_metrics_icon() -> PIL.Image.Image:
    """シャッターメトリクス用のアイコンを動的生成（アンチエイリアス対応）"""
    # アンチエイリアスのため4倍サイズで描画してから縮小
    scale = 4
    size = 32
    large_size = size * scale

    # 大きなサイズで描画
    img = PIL.Image.new("RGBA", (large_size, large_size), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(img)

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
    return img.resize((size, size), PIL.Image.Resampling.LANCZOS)
