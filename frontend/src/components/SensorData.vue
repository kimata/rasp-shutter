<template>
    <div class="mb-4">
        <h2>センサー値</h2>
        <div class="mt-4 mb-2">
            <table class="w-full">
                <thead>
                    <tr class="border-b">
                        <th class="text-left py-2 w-1/6">センサー</th>
                        <th colspan="2" class="text-center py-2 w-1/3">値</th>
                        <th colspan="2" class="text-left py-2 w-1/2">最新更新日時</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="name in ['solar_rad', 'lux', 'altitude']" :key="name" class="border-b">
                        <td class="text-left py-2">{{ this.SENSOR_DEF[name].label }}</td>
                        <td class="text-right py-2">
                            <span v-if="sensor[name].valid">
                                <b>{{ this.sensorValue(name) }}</b>
                            </span>
                            <span v-else>?</span>
                        </td>
                        <td class="text-left py-2 pl-2">
                            <small v-html="this.SENSOR_DEF[name].unit" />
                        </td>
                        <td class="text-left py-2">
                            <span v-if="sensor[name].valid">{{ sensor[name].time.fromNow() }}</span>
                            <span v-else>不明</span>
                        </td>
                        <td class="text-left py-2 whitespace-nowrap">
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
                altitude: { valid: false },
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

                this.displayValues[name] = fromValue + valueDiff * easeProgress;

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

<style></style>
