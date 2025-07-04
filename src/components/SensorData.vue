<template>
    <div class="row mb-4">
        <div class="col-xl-6 offset-xl-3 col-lg-8 offset-lg-2 col-md-10 offset-md-1">
            <h2>センサー値</h2>
            <div class="container mt-4 mb-2">
                <table className="table">
                    <thead>
                        <tr className="row">
                            <th className="col-2">センサー</th>
                            <th colSpan="2" className="col-4 text-center">値</th>
                            <th colSpan="2" className="col-6">最新更新日時</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="name in ['lux', 'solar_rad', 'altitude']" :key="name" className="row">
                            <td class="text-start col-2">{{ this.SENSOR_DEF[name].label }}</td>
                            <td class="text-end col-2">
                                <span v-if="sensor[name].valid">
                                    <b>{{ this.sensorValue(name) }}</b>
                                </span>
                                <span v-else>?</span>
                            </td>
                            <td class="text-start col-2">
                                <small v-html="this.SENSOR_DEF[name].unit" />
                            </td>
                            <td class="text-start col-2">
                                <span v-if="sensor[name].valid">{{ sensor[name].time.fromNow() }}</span>
                                <span v-else>不明</span>
                            </td>
                            <td class="text-start col-4 text-nowrap">
                                <span v-if="sensor[name].valid">{{
                                    sensor[name].time.format("M/D HH:mm")
                                }}</span>
                                <span v-else>不明</span>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</template>

<script>
import axios from "axios";

import "dayjs/locale/ja";
import dayjs from "dayjs";
dayjs.locale("ja");

import AppConfig from "../mixins/AppConfig.js";

const SENSOR_DEF = {
    solar_rad: {
        label: "日射",
        unit: "W/m<sup>2</sup>",
    },
    lux: {
        label: "照度",
        unit: "LUX",
    },
    altitude: {
        label: "太陽高度",
        unit: "度",
    },
};

export default {
    name: "sensor-data",
    mixins: [AppConfig],
    data() {
        return {
            sensor: {
                lux: { valid: false },
                solar_rad: { valid: false },
            },
            animatingValues: {},
            displayValues: {},
            interval: null,
        };
    },
    compatConfig: { MODE: 3 },
    created() {
        this.SENSOR_DEF = SENSOR_DEF;
        this.updateSensor();
        this.interval = setInterval(() => {
            this.updateSensor();
        }, 10000);
    },
    unmounted() {
        if (this.interval == null) {
            return;
        }
        clearInterval(this.interval);
    },
    methods: {
        updateSensor: function () {
            axios
                .get(this.AppConfig["apiEndpoint"] + "sensor")
                .then((response) => {
                    const oldSensor = { ...this.sensor };
                    this.sensor = response.data;

                    ["solar_rad", "lux", "altitude"].forEach((name) => {
                        this.sensor[name].time = dayjs(this.sensor[name].time);

                        // アニメーション処理
                        if (this.sensor[name].valid && oldSensor[name] && oldSensor[name].valid) {
                            const oldValue = Number(oldSensor[name].value);
                            const newValue = Number(this.sensor[name].value);

                            if (oldValue !== newValue) {
                                this.animateValue(name, oldValue, newValue);
                            }
                        } else if (this.sensor[name].valid) {
                            // 初回または無効から有効になった場合
                            this.displayValues[name] = Number(this.sensor[name].value);
                        }
                    });
                })
                .catch(() => {
                    this.$root.$toast.open({
                        type: "error",
                        position: "top-right",
                        message: "センサデータの取得に失敗しました。",
                    });
                });
        },
        sensorValue: function (name) {
            if (this.displayValues[name] !== undefined) {
                return Math.round(this.displayValues[name]).toLocaleString();
            }
            if (this.sensor[name].valid) {
                return Math.round(Number(this.sensor[name].value)).toLocaleString();
            } else {
                return "-";
            }
        },
        animateValue: function (name, fromValue, toValue, duration = 1000) {
            if (this.animatingValues[name]) {
                clearInterval(this.animatingValues[name]);
            }

            const startTime = Date.now();
            const valueDiff = toValue - fromValue;

            this.animatingValues[name] = setInterval(() => {
                const elapsed = Date.now() - startTime;
                const progress = Math.min(elapsed / duration, 1);

                // easeOutQuart for smoother animation
                const easeProgress = 1 - Math.pow(1 - progress, 4);

                this.displayValues[name] = fromValue + (valueDiff * easeProgress);

                if (progress >= 1) {
                    clearInterval(this.animatingValues[name]);
                    delete this.animatingValues[name];
                    this.displayValues[name] = toValue;
                }
            }, 16); // ~60fps
        },
    },
};
</script>

<style>
.page-link {
    color: #28a745 !important;
}
.page-item.active .page-link {
    background-color: #28a745 !important;
    border-color: #28a745 !important;
    color: #ffffff !important;
}
</style>
