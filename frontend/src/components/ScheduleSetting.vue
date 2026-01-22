<template>
    <div class="mb-4 mt-4">
        <h2>自動</h2>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
                <ScheduleEntry label="オープン" name="open" v-model="current.open" />
            </div>
            <div>
                <ScheduleEntry label="クローズ" name="close" v-model="current.close" />
            </div>
        </div>
        <div class="mt-4 mb-2">
            <button
                type="button"
                class="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded flex items-center justify-center gap-2"
                @click="save()"
                v-bind:disabled="!isChanged"
                data-testid="save"
            >
                <CloudArrowUpIcon class="w-5 h-5" />
                保存
            </button>
        </div>
    </div>
</template>

<script>
import axios from "axios";
import { CloudArrowUpIcon } from "@heroicons/vue/24/outline";
import AppConfig from "../mixins/AppConfig.js";
import ScheduleEntry from "./ScheduleEntry.vue";

export default {
    name: "schedule-setting",
    mixins: [AppConfig],
    components: {
        ScheduleEntry,
        CloudArrowUpIcon,
    },
    compatConfig: { MODE: 3 },
    data() {
        return {
            current: {
                open: {
                    is_active: false,
                    time: "00:00",
                    wday: Array(7).fill(false),
                    solar_rad: 0,
                    lux: 0,
                    altitude: 0,
                },
                close: {
                    is_active: false,
                    time: "00:00",
                    wday: Array(7).fill(false),
                    solar_rad: 0,
                    lux: 0,
                    altitude: 0,
                },
            },
            saved: {
                open: {
                    is_active: false,
                    time: "00:00",
                    wday: Array(7).fill(false),
                    solar_rad: 0,
                    lux: 0,
                    altitude: 0,
                },
                close: {
                    is_active: false,
                    time: "00:00",
                    wday: Array(7).fill(false),
                    solar_rad: 0,
                    lux: 0,
                    altitude: 0,
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
            axios
                .get(this.AppConfig["apiEndpoint"] + "schedule_ctrl", {
                    params: { cmd: "set", data: JSON.stringify(this.current) },
                })
                .then((response) => {
                    this.saved = response.data;
                    this.$root.$toast.open({
                        type: "success",
                        position: "top-right",
                        message: "正常に保存できました。",
                    });
                })
                .catch(() => {
                    this.$root.$toast.open({
                        type: "error",
                        position: "top-right",
                        message: "保存に失敗しました。",
                    });
                });
        },
        isStateDiffer: function (a, b) {
            for (let mode in a) {
                // Check all properties in a[mode]
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
            this.eventSource.onerror = () => {
                if (this.eventSource.readyState == 2) {
                    this.eventSource.close();
                    setTimeout(this.watchEvent, 10000);
                }
            };
        },
    },
};
</script>

<style scoped></style>
