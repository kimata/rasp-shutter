<template>
    <div class="row mb-4 mt-4">
        <div class="col-xl-6 offset-xl-3 col-lg-8 offset-lg-2 col-md-10 offset-md-1">
            <h2>自動</h2>
            <form class="schedule-setting">
                <div class="row">
                    <div class="col-lg-6 col-md-12">
                        <ScheduleEntry label="オープン" name="open" v-model="current.open" />
                    </div>
                    <div class="col-lg-6 col-md-12">
                        <ScheduleEntry label="クローズ" name="close" v-model="current.close" />
                    </div>
                </div>
                <div class="container mt-4 mb-2">
                    <button
                        type="button"
                        class="btn btn-success col-12"
                        @click="save()"
                        v-bind:disabled="!isChanged"
                        data-testid="save"
                    >
                        <i class="bi bi-save" />
                        保存
                    </button>
                </div>
            </form>
        </div>
    </div>
</template>

<script>
import axios from "axios";
import AppConfig from "../mixins/AppConfig.js";
import ScheduleEntry from "./ScheduleEntry";

export default {
    name: "schedule-setting",
    mixins: [AppConfig],
    components: {
        ScheduleEntry,
    },
    compatConfig: { MODE: 3 },
    data() {
        return {
            current: {
                open: {
                    is_active: false,
                    time: "00:00",
                    wday: Array(7).fill(false),
                },
                close: {
                    is_active: false,
                    time: "00:00",
                    wday: Array(7).fill(false),
                },
            },
            saved: {
                open: {
                    is_active: false,
                },
                close: {
                    is_active: false,
                },
            },
        };
    },
    created() {
        this.updateSchedule();
        this.watchEvent();
    },
    computed: {
        isChanged: function () {
            return this.isStateDiffer(this.current, this.saved);
        },
    },

    methods: {
        updateSchedule: function () {
            axios
                .get(this.AppConfig["apiEndpoint"] + "schedule_ctrl")
                .then((response) => {
                    this.current = response.data;
                    this.saved = JSON.parse(JSON.stringify(response.data)); // NOTE: deep copy
                })
                .catch(() => {
                    this.$root.$toast.open({
                        type: "error",
                        position: "top-right",
                        message: "スケジュールデータの取得に失敗しました。",
                    });
                });
        },
        save: function () {
            console.log(this.current);
            axios
                .get(this.AppConfig["apiEndpoint"] + "schedule_ctrl", {
                    params: { cmd: "set", data: JSON.stringify(this.current) },
                })
                .then((response) => {
                    this.saved = response.data;
                    this.$root.$toast.open({
                        type: "success",
                        position: "top-right",
                        message: "正常に保存できました．",
                    });
                })
                .catch(() => {
                    this.$root.$toast.open({
                        type: "error",
                        position: "top-right",
                        message: "保存に失敗しました．",
                    });
                });
        },
        isStateDiffer: function (a, b) {
            for (let mode in a) {
                for (let key in a[mode]) {
                    if (key == "wday") {
                        if (JSON.stringify(a[mode]["wday"]) !== JSON.stringify(b[mode]["wday"])) {
                            return true;
                        }
                    } else {
                        if (a[mode][key] !== b[mode][key]) {
                            return true;
                        }
                    }
                }
            }
            return false;
        },
        watchEvent: function () {
            this.eventSource = new EventSource(this.AppConfig["apiEndpoint"] + "event");
            this.eventSource.addEventListener("message", (e) => {
                if (e.data == "schedule") {
                    this.updateSchedule();
                }
            });
        },
    },
};
</script>

<style scoped></style>
