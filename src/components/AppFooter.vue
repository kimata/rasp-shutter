<template>
    <div class="p-1 float-end text-end">
        <small>
            <p class="text-muted m-0">
                <small>イメージビルド: {{ sysinfo.imageBuildDate }} [{{ sysinfo.imageBuildDateFrom }}]</small>
            </p>
            <p class="text-muted m-0">
                <small>Vueビルド: {{ build.date }} [{{ build.dateFrom }}]</small>
            </p>
            <p class="text-muted m-0">
                <small>Vue バージョン: {{ vueVersion }}</small>
            </p>
            <p class="text-muted m-0">
                <small>起動日時: {{ sysinfo.uptime }} [{{ sysinfo.uptimeFrom }}]</small>
            </p>
            <p class="text-muted m-0">
                <small>サーバ時刻: {{ sysinfo.date }} [{{ sysinfo.timezone }}]</small>
            </p>
            <p class="text-muted m-0">
                <small>load average: {{ sysinfo.loadAverage }}</small>
            </p>
        </small>
        <p class="display-6">
            <a :href="AppConfig['apiEndpoint'] + 'metrics'" class="text-secondary me-3">
                <i class="bi bi-graph-up" />
            </a>
            <a href="https://github.com/kimata/rasp-shutter/" class="text-secondary">
                <i class="bi bi-github" />
            </a>
        </p>
    </div>
</template>

<script>
import axios from "axios";
import "dayjs/locale/ja";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import localizedFormat from "dayjs/plugin/localizedFormat";
dayjs.locale("ja");
dayjs.extend(relativeTime);
dayjs.extend(localizedFormat);

import AppConfig from "../mixins/AppConfig.js";
import { version } from "vue";

export default {
    name: "app-footer",
    mixins: [AppConfig],
    data() {
        return {
            vueVersion: version,
            build: {
                date: dayjs(document.documentElement.dataset.buildDate).format("llll"),
                dateFrom: dayjs(document.documentElement.dataset.buildDate).fromNow(),
            },
            sysinfo: {
                imageBuildDate: "?",
                imageBuildDateFrom: "?",
                date: "",
                uptime: "",
                uptimeFrom: "",
                loadAverage: "",
            },
        };
    },
    compatConfig: { MODE: 3 },
    created() {
        this.updateSysinfo();
    },
    methods: {
        updateSysinfo: function () {
            axios
                .get(this.AppConfig["apiEndpoint"] + "sysinfo")
                .then((response) => {
                    const date = dayjs(response.data["date"]);
                    const uptime = dayjs(response.data["uptime"]);

                    if (response.data["image_build_date"] !== "") {
                        const imageBuildDate = dayjs(response.data["image_build_date"]);
                        this.sysinfo.imageBuildDate = imageBuildDate.format("llll");
                        this.sysinfo.imageBuildDateFrom = imageBuildDate.fromNow();
                    } else {
                        this.sysinfo.imageBuildDate = "?";
                        this.sysinfo.imageBuildDateFrom = "?";
                    }

                    this.sysinfo.date = date.format("llll");
                    this.sysinfo.timezone = response.data["timezone"];
                    this.sysinfo.uptime = uptime.format("llll");
                    this.sysinfo.uptimeFrom = uptime.fromNow();
                    this.sysinfo.loadAverage = response.data["load_average"];
                })
                .catch(() => {});
        },
    },
};
</script>

<style></style>
