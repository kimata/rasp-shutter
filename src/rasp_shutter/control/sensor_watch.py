#!/usr/bin/env python3
"""
センサー値の張り付き監視

太陽が十分に高いのにセンサー値が 0 のままの状態が続いた場合、センサー故障として警告します。

センサー値が「有効な 0」のまま張り付くと、開ける条件（閾値より大きい）が成立せず、
エラーにもならないままシャッターが開かなくなるため、値そのものの異常を検知します。
"""

import datetime
from dataclasses import dataclass

import my_lib.webapp.log

import rasp_shutter.control.config
import rasp_shutter.control.webapi.control
import rasp_shutter.type_defs

# 監視対象のセンサー（SensorData の属性名）と表示名
SENSOR_LABELS = {
    "lux": "照度センサ",
    "solar_rad": "日射センサ",
}


@dataclass
class _WatchState:
    """センサーごとの監視状態

    Attributes
    ----------
        zero_since: 太陽が高い状態で値が 0 になり始めた時刻（該当しない場合は None）
        notified_date: 最後に異常を通知した日付（未通知または復旧済みの場合は None）

    """

    zero_since: datetime.datetime | None = None
    notified_date: datetime.date | None = None


class SensorStuckWatcher:
    """センサー値の張り付きを監視する

    状態はメモリ上にのみ保持する。プロセス再起動後は継続時間の計測からやり直しになる。
    """

    def __init__(self) -> None:
        self._states = {name: _WatchState() for name in SENSOR_LABELS}

    def check(self, sense_data: rasp_shutter.type_defs.SensorData, now: datetime.datetime) -> None:
        """センサー値を確認し、張り付きを検知したら警告する

        異常が続いている間は、1 日 1 回のペースで再通知する。
        """
        cfg = rasp_shutter.control.config
        altitude = sense_data.altitude
        is_daylight = (
            altitude.valid
            and altitude.value is not None
            and altitude.value >= cfg.SENSOR_STUCK_ALTITUDE_MIN_DEG
        )

        stuck_labels = []
        for name, label in SENSOR_LABELS.items():
            state = self._states[name]
            sensor_value: rasp_shutter.type_defs.SensorValue = getattr(sense_data, name)

            if sensor_value.valid and sensor_value.value is not None and sensor_value.value > 0:
                if state.notified_date is not None:
                    my_lib.webapp.log.info(f"😊 {label}の値が 0 以外に戻りました。")
                state.zero_since = None
                state.notified_date = None
            elif not is_daylight or not sensor_value.valid:
                # NOTE: 夜間は 0 が正常値なので判定しない。値が取得できない場合は、
                # スケジュール制御側で別途エラーになるので、ここでは扱わない。
                state.zero_since = None
            else:
                if state.zero_since is None:
                    state.zero_since = now

                elapsed_sec = (now - state.zero_since).total_seconds()
                if elapsed_sec >= cfg.SENSOR_STUCK_DURATION_SEC and state.notified_date != now.date():
                    state.notified_date = now.date()
                    stuck_labels.append(label)

        if stuck_labels:
            # NOTE: Slack 通知はアプリ単位でレート制限されるため、1 メッセージにまとめる。
            stuck_text = "と".join(stuck_labels)
            sensor_text = rasp_shutter.control.webapi.control.sensor_text(sense_data)
            my_lib.webapp.log.error(
                f"😵 太陽が出ているのに{stuck_text}の値が "
                f"{cfg.SENSOR_STUCK_DURATION_SEC // 60} 分以上 0 のままです。"
                f"センサーが故障している可能性があります。{sensor_text}"
            )
