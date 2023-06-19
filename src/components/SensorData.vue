<template>
    <div class="row mb-4">
        <div class="col-xl-6 offset-xl-3 col-lg-8 offset-lg-2 col-md-10 offset-md-1">
            <h2>センサー値</h2>
            <div class="container mt-4 mb-2">
                <table className="table">
                    <thead>
                        <tr className="row">
                            <th className="col-3">センサー</th>
                            <th colSpan="2" className="col-3">値</th>
                            <th colSpan="2" className="col-6">最新更新日時</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="name in ['lux', 'solar_rad']" :key="name" className="row">
                            <td class="text-start col-3">{{ this.SENSOR_DEF[name].label }}</td>
                            <td class="text-end col-1">
                                <span v-if="sensor[name].valid">
                                    <b>{{ this.sensorValue(name) }}</b>
                                </span>
                                <span v-else>?</span>
                            </td>
                            <td class="text-start col-2">
                                <small v-html="this.SENSOR_DEF[name].unit" />
                            </td>
                            <td class="text-start col-2">
                                <span v-if="sensor[name].valid">{{ sensor.lux.time.fromNow() }}</span>
                                <span v-else>不明</span>
                            </td>
                            <td class="text-end col-4">
                                <span v-if="sensor[name].valid">{{
                                    sensor.lux.time.format("YYYY-MM-DD HH:mm:ss")
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
import moment from "moment";
import "moment/locale/ja";
import AppConfig from "../mixins/AppConfig.js";

const SENSOR_DEF = {
    solar_rad: {
        label: "日射",
        unit: "W/mm<sup>2</sup>",
    },
    lux: {
        label: "照度",
        unit: "LUX",
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
                    this.sensor = response.data;

                    ["solar_rad", "lux"].forEach((name) => {
                        this.sensor[name].time = moment(this.sensor[name].time);
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
            if (this.sensor[name].valid) {
                return Number(this.sensor[name].value).toFixed();
            } else {
                return "-";
            }
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
