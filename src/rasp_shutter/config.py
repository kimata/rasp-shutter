#!/usr/bin/env python3
"""
設定ファイルの型定義

設計方針:
- dataclass で型安全な設定を定義
- パスは pathlib.Path で統一
- None の使用を最小限に
- my_lib の型を直接使用
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any

import my_lib.config
import my_lib.notify.slack
import my_lib.sensor_data
import my_lib.webapp.config

# my_lib から re-export
InfluxDBConfig = my_lib.sensor_data.InfluxDBConfig
SlackErrorOnlyConfig = my_lib.notify.slack.SlackErrorOnlyConfig
SlackEmptyConfig = my_lib.notify.slack.SlackEmptyConfig
SlackErrorConfig = my_lib.notify.slack.SlackErrorConfig
SlackChannelConfig = my_lib.notify.slack.SlackChannelConfig

# Slack 設定の型エイリアス
SlackConfigType = SlackErrorOnlyConfig | SlackEmptyConfig

__all__ = [
    "AppConfig",
    "InfluxDBConfig",
    "LivenessConfig",
    "LivenessFileConfig",
    "LocationConfig",
    "MetricsConfig",
    "SensorConfig",
    "SensorSpecConfig",
    "ShutterConfig",
    "ShutterEndpointConfig",
    "SlackChannelConfig",
    "SlackConfigType",
    "SlackEmptyConfig",
    "SlackErrorConfig",
    "SlackErrorOnlyConfig",
    "WebappConfig",
    "WebappDataConfig",
    "load",
    "parse_config",
]


# === Webapp ===
@dataclass(frozen=True)
class WebappDataConfig:
    """webapp.data セクションの設定"""

    schedule_file_path: pathlib.Path
    log_file_path: pathlib.Path
    stat_dir_path: pathlib.Path


@dataclass(frozen=True)
class WebappConfig:
    """webapp セクションの設定"""

    static_dir_path: pathlib.Path
    data: WebappDataConfig


# === Sensor ===
@dataclass(frozen=True)
class SensorSpecConfig:
    """センサー指定"""

    name: str
    measure: str
    hostname: str


@dataclass(frozen=True)
class SensorConfig:
    """sensor セクションの設定"""

    influxdb: InfluxDBConfig
    lux: SensorSpecConfig
    solar_rad: SensorSpecConfig


# === Location ===
@dataclass(frozen=True)
class LocationConfig:
    """location セクションの設定"""

    latitude: float
    longitude: float


# === Metrics ===
@dataclass(frozen=True)
class MetricsConfig:
    """metrics セクションの設定"""

    data: pathlib.Path


# === Liveness ===
@dataclass(frozen=True)
class LivenessFileConfig:
    """Liveness ファイルパス設定"""

    scheduler: pathlib.Path


@dataclass(frozen=True)
class LivenessConfig:
    """liveness セクションの設定"""

    file: LivenessFileConfig


# === Shutter ===
@dataclass(frozen=True)
class ShutterEndpointConfig:
    """シャッターエンドポイント設定"""

    open: str
    close: str


@dataclass(frozen=True)
class ShutterConfig:
    """シャッター設定"""

    name: str
    endpoint: ShutterEndpointConfig


# === メイン設定クラス ===
@dataclass(frozen=True)
class AppConfig:
    """アプリケーション設定"""

    webapp: WebappConfig
    sensor: SensorConfig
    location: LocationConfig
    metrics: MetricsConfig
    liveness: LivenessConfig
    shutter: list[ShutterConfig]
    slack: SlackConfigType


# === パース関数 ===
def _parse_webapp_data(data: dict[str, Any]) -> WebappDataConfig:
    return WebappDataConfig(
        schedule_file_path=pathlib.Path(data["schedule_file_path"]).resolve(),
        log_file_path=pathlib.Path(data["log_file_path"]).resolve(),
        stat_dir_path=pathlib.Path(data["stat_dir_path"]).resolve(),
    )


def _parse_webapp(data: dict[str, Any]) -> WebappConfig:
    return WebappConfig(
        static_dir_path=pathlib.Path(data["static_dir_path"]).resolve(),
        data=_parse_webapp_data(data["data"]),
    )


def _parse_sensor_spec(data: dict[str, Any]) -> SensorSpecConfig:
    return SensorSpecConfig(
        name=data["name"],
        measure=data["measure"],
        hostname=data["hostname"],
    )


def _parse_influxdb(data: dict[str, Any]) -> InfluxDBConfig:
    return InfluxDBConfig(
        url=data["url"],
        org=data["org"],
        token=data["token"],
        bucket=data["bucket"],
    )


def _parse_sensor(data: dict[str, Any]) -> SensorConfig:
    return SensorConfig(
        influxdb=_parse_influxdb(data["influxdb"]),
        lux=_parse_sensor_spec(data["lux"]),
        solar_rad=_parse_sensor_spec(data["solar_rad"]),
    )


def _parse_location(data: dict[str, Any]) -> LocationConfig:
    return LocationConfig(
        latitude=float(data["latitude"]),
        longitude=float(data["longitude"]),
    )


def _parse_metrics(data: dict[str, Any]) -> MetricsConfig:
    return MetricsConfig(
        data=pathlib.Path(data["data"]).resolve(),
    )


def _parse_slack(data: dict[str, Any] | None) -> SlackConfigType:
    """Slack 設定をパースする"""
    if data is None or not data.get("bot_token"):
        return SlackEmptyConfig()

    return SlackErrorOnlyConfig(
        bot_token=data["bot_token"],
        from_name=data["from"],
        error=SlackErrorConfig(
            channel=SlackChannelConfig(
                name=data["error"]["channel"]["name"],
                id=data["error"]["channel"]["id"],
            ),
            interval_min=int(data["error"]["interval_min"]),
        ),
    )


def _parse_liveness_file(data: dict[str, Any]) -> LivenessFileConfig:
    return LivenessFileConfig(
        scheduler=pathlib.Path(data["scheduler"]).resolve(),
    )


def _parse_liveness(data: dict[str, Any]) -> LivenessConfig:
    return LivenessConfig(
        file=_parse_liveness_file(data["file"]),
    )


def _parse_shutter_endpoint(data: dict[str, Any]) -> ShutterEndpointConfig:
    return ShutterEndpointConfig(
        open=data["open"],
        close=data["close"],
    )


def _parse_shutter(data: dict[str, Any]) -> ShutterConfig:
    return ShutterConfig(
        name=data["name"],
        endpoint=_parse_shutter_endpoint(data["endpoint"]),
    )


def _parse_shutter_list(data: list[dict[str, Any]]) -> list[ShutterConfig]:
    return [_parse_shutter(item) for item in data]


def parse_config(data: dict[str, Any]) -> AppConfig:
    """設定辞書をパースして AppConfig を返す"""
    return AppConfig(
        webapp=_parse_webapp(data["webapp"]),
        sensor=_parse_sensor(data["sensor"]),
        location=_parse_location(data["location"]),
        metrics=_parse_metrics(data["metrics"]),
        liveness=_parse_liveness(data["liveness"]),
        shutter=_parse_shutter_list(data["shutter"]),
        slack=_parse_slack(data.get("slack")),
    )


def to_my_lib_webapp_config(config: AppConfig) -> my_lib.webapp.config.WebappConfig:
    """AppConfig から my_lib.webapp.config.WebappConfig を生成"""
    return my_lib.webapp.config.WebappConfig(
        static_dir_path=config.webapp.static_dir_path,
        data=my_lib.webapp.config.WebappDataConfig(
            schedule_file_path=config.webapp.data.schedule_file_path,
            log_file_path=config.webapp.data.log_file_path,
            stat_dir_path=config.webapp.data.stat_dir_path,
        ),
    )


def load(config_path: str, schema_path: pathlib.Path) -> AppConfig:
    """設定ファイルを読み込んで AppConfig を返す"""
    raw_config = my_lib.config.load(config_path, schema_path)
    return parse_config(raw_config)
