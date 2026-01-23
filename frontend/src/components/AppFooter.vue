<template>
    <div class="p-4 float-right text-right mt-8">
        <small>
            <p class="text-gray-500 m-0">
                <small>イメージビルド: {{ sysinfo.imageBuildDate }} [{{ sysinfo.imageBuildDateFrom }}]</small>
            </p>
            <p class="text-gray-500 m-0">
                <small>Vueビルド: {{ build.date }} [{{ build.dateFrom }}]</small>
            </p>
            <p class="text-gray-500 m-0">
                <small>Vue バージョン: {{ vueVersion }}</small>
            </p>
            <p class="text-gray-500 m-0">
                <small>起動日時: {{ sysinfo.uptime }} [{{ sysinfo.uptimeFrom }}]</small>
            </p>
            <p class="text-gray-500 m-0">
                <small>サーバ時刻: {{ sysinfo.date }} [{{ sysinfo.timezone }}]</small>
            </p>
            <p class="text-gray-500 m-0">
                <small>load average: {{ sysinfo.loadAverage }}</small>
            </p>
        </small>
        <p class="text-2xl">
            <a :href="AppConfig['apiEndpoint'] + 'metrics'" class="text-gray-600 hover:text-gray-800 mr-3">
                <ChartBarIcon class="w-6 h-6 inline" />
            </a>
            <a href="https://github.com/kimata/rasp-shutter/" class="text-gray-600 hover:text-gray-800">
                <svg class="w-6 h-6 inline" fill="currentColor" viewBox="0 0 24 24">
                    <path
                        fill-rule="evenodd"
                        d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                        clip-rule="evenodd"
                    />
                </svg>
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

import { ChartBarIcon } from "@heroicons/vue/24/outline";
import AppConfig from "../mixins/AppConfig.js";
import { version } from "vue";

export default {
    name: "app-footer",
    mixins: [AppConfig],
    components: {
        ChartBarIcon,
    },
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
