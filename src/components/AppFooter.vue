<template>
    <div class="p-1 float-end text-end">
        <small>
            <p class="text-muted m-0">
                <small>イメージ: {{ sysinfo.imageBuildDate }} [{{ build.imageBuildDateFrom }}]</small>
            </p>
            <p class="text-muted m-0">
                <small>Vue: {{ build.date }} [{{ build.dateFrom }}]</small>
            </p>
            <p class="text-muted m-0">
                <small>起動日時: {{ sysinfo.uptime }} [{{ sysinfo.uptimeFrom }}]</small>
            </p>
            <p class="text-muted m-0">
                <small>サーバ時刻: {{ sysinfo.date }}</small>
            </p>
            <p class="text-muted m-0">
                <small>load average: {{ sysinfo.loadAverage }}</small>
            </p>
        </small>
        <p class="display-6">
            <a href="https://github.com/kimata/rasp-shutter/" class="text-secondary">
                <i class="bi bi-github" />
            </a>
        </p>
    </div>
</template>

<script>
import axios from "axios";
import AppConfig from "../mixins/AppConfig.js";
import moment from "moment";
import "moment/locale/ja";

export default {
    name: "app-footer",
    mixins: [AppConfig],
    data() {
        return {
            build: {
                date: moment(document.documentElement.dataset.buildDate).format("lll"),
                dateFrom: moment(document.documentElement.dataset.buildDate).fromNow(),
            },
            sysinfo: {
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
                    const date = moment(response.data["date"]);
                    const uptime = moment(response.data["uptime"]);

                    if (response.data["image_build_date"] !== "") {
                        const imageBuildDate = moment(response.data["image_build_date"]);
                        this.sysinfo.imageBuildDate = imageBuildDate.format("llll");
                        this.sysinfo.imageBuildDateFrom = imageBuildDate.fromNow();
                    } else {
                        this.sysinfo.image_build_date = "";
                    }

                    this.sysinfo.date = date.format("llll");
                    this.sysinfo.uptime = uptime.format("llll");
                    this.sysinfo.uptimeFrom = uptime.fromNow();
                    this.sysinfo.loadAverage = response.data["loadAverage"];
                })
                .catch(() => {});
        },
    },
};
</script>

<style></style>
