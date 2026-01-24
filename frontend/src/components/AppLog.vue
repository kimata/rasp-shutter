<template>
    <div>
        <h2 class="text-xl font-semibold text-gray-800 flex items-center gap-2 mb-4">
            <ClipboardDocumentListIcon class="w-6 h-6 text-green-600" />
            実行ログ
        </h2>
        <div class="log mt-4">
            <p v-if="log.length == 0" class="text-gray-500 text-center py-4">ログがありません。</p>
            <div v-else class="space-y-3">
                <div
                    v-for="(entry, index) in log.slice((page - 1) * pageSize, page * pageSize)"
                    :key="index"
                    class="flex gap-4 p-4 rounded-xl bg-white border border-gray-200 transition-all hover:shadow-md"
                >
                    <!-- アイコン部分 -->
                    <div class="flex-shrink-0 flex flex-col items-center w-16">
                        <div
                            class="w-12 h-12 rounded-full flex items-center justify-center"
                            :class="getIconBgClass(entry)"
                        >
                            <component
                                :is="getIcon(entry)"
                                class="w-6 h-6"
                                :class="getIconClass(entry)"
                            />
                        </div>
                        <span
                            class="mt-1 text-xs font-medium"
                            :class="getIconClass(entry)"
                        >
                            {{ getLabel(entry) }}
                        </span>
                    </div>

                    <!-- コンテンツ部分 -->
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-1">
                            <span class="text-sm text-gray-500">{{ entry.fromNow }}</span>
                        </div>
                        <div
                            class="log-message text-gray-700 text-sm leading-relaxed"
                            v-html="formatMessage(entry.message)"
                        ></div>
                        <div class="text-xs text-gray-400 mt-1">{{ entry.date }}</div>
                    </div>
                </div>

                <!-- Pagination -->
                <nav v-if="totalPages > 1" class="flex justify-center mt-4">
                    <ul class="flex gap-1">
                        <li>
                            <button
                                @click="page = Math.max(1, page - 1)"
                                :disabled="page === 1"
                                class="px-3 py-1 border rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                            >
                                &laquo;
                            </button>
                        </li>
                        <li v-for="p in visiblePages" :key="p">
                            <button
                                @click="page = p"
                                :class="[
                                    'px-3 py-1 border rounded',
                                    page === p
                                        ? 'bg-green-600 text-white border-green-600'
                                        : 'hover:bg-gray-100 text-green-600',
                                ]"
                            >
                                {{ p }}
                            </button>
                        </li>
                        <li>
                            <button
                                @click="page = Math.min(totalPages, page + 1)"
                                :disabled="page === totalPages"
                                class="px-3 py-1 border rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                            >
                                &raquo;
                            </button>
                        </li>
                    </ul>
                </nav>
            </div>
        </div>
        <div class="mt-6">
            <button
                type="button"
                class="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-3 px-4 rounded flex items-center justify-center gap-2"
                @click="clear()"
                data-testid="clear"
            >
                <XCircleIcon class="w-5 h-5" />
                クリア
            </button>
        </div>
    </div>
</template>

<script>
import axios from "axios";
import {
    XCircleIcon,
    ClipboardDocumentListIcon,
    ArrowUpIcon,
    ArrowDownIcon,
    ExclamationCircleIcon,
    ClockIcon,
    CalendarDaysIcon,
    ArrowPathIcon,
    BellAlertIcon,
    InformationCircleIcon,
    SunIcon,
    MoonIcon,
} from "@heroicons/vue/24/outline";

import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import localizedFormat from "dayjs/plugin/localizedFormat";

dayjs.locale("ja");
dayjs.extend(relativeTime);
dayjs.extend(localizedFormat);

import AppConfig from "../mixins/AppConfig.js";

// ログ種別の定義
const LOG_TYPES = {
    OPEN_SUCCESS: "open_success",
    CLOSE_SUCCESS: "close_success",
    SENSOR_OPEN: "sensor_open",
    SENSOR_CLOSE: "sensor_close",
    ERROR: "error",
    POSTPONE: "postpone",
    SCHEDULE: "schedule",
    SYSTEM: "system",
    INFO: "info",
};

// ログ種別を判定する関数
function detectLogType(message) {
    // エラー・失敗系
    if (message.includes("😵") || message.includes("失敗")) {
        return LOG_TYPES.ERROR;
    }
    // スケジュール更新
    if (message.includes("📅") || message.includes("スケジュールを更新")) {
        return LOG_TYPES.SCHEDULE;
    }
    // システム（再起動等）
    if (message.includes("🏃") || message.includes("再起動")) {
        return LOG_TYPES.SYSTEM;
    }
    // センサー制御（照度による開閉）
    if (message.includes("🌅")) {
        return LOG_TYPES.SENSOR_OPEN;
    }
    if (message.includes("🌇")) {
        return LOG_TYPES.SENSOR_CLOSE;
    }
    // 見合わせ・延期
    if (
        message.includes("🔔") ||
        message.includes("📝") ||
        message.includes("見合わせ") ||
        message.includes("延期")
    ) {
        return LOG_TYPES.POSTPONE;
    }
    // シャッター開け成功
    if (message.includes("開けました")) {
        return LOG_TYPES.OPEN_SUCCESS;
    }
    // シャッター閉め成功
    if (message.includes("閉めました")) {
        return LOG_TYPES.CLOSE_SUCCESS;
    }
    // その他
    return LOG_TYPES.INFO;
}

export default {
    name: "app-log",
    mixins: [AppConfig],
    components: {
        XCircleIcon,
        ClipboardDocumentListIcon,
        ArrowUpIcon,
        ArrowDownIcon,
        ExclamationCircleIcon,
        ClockIcon,
        CalendarDaysIcon,
        ArrowPathIcon,
        BellAlertIcon,
        InformationCircleIcon,
        SunIcon,
        MoonIcon,
    },
    data() {
        return {
            pageSize: 10,
            page: 1,
            log: [],
            eventSource: null,
        };
    },
    compatConfig: { MODE: 3 },
    computed: {
        totalPages() {
            return Math.ceil(this.log.length / this.pageSize);
        },
        visiblePages() {
            const pages = [];
            const start = Math.max(1, this.page - 2);
            const end = Math.min(this.totalPages, this.page + 2);
            for (let i = start; i <= end; i++) {
                pages.push(i);
            }
            return pages;
        },
    },
    created() {
        this.watchEvent();
        this.updateLog();
    },
    methods: {
        getLogType(entry) {
            return detectLogType(entry.message);
        },
        getIcon(entry) {
            const type = this.getLogType(entry);
            const iconMap = {
                [LOG_TYPES.OPEN_SUCCESS]: "ArrowUpIcon",
                [LOG_TYPES.CLOSE_SUCCESS]: "ArrowDownIcon",
                [LOG_TYPES.SENSOR_OPEN]: "SunIcon",
                [LOG_TYPES.SENSOR_CLOSE]: "MoonIcon",
                [LOG_TYPES.ERROR]: "ExclamationCircleIcon",
                [LOG_TYPES.POSTPONE]: "ClockIcon",
                [LOG_TYPES.SCHEDULE]: "CalendarDaysIcon",
                [LOG_TYPES.SYSTEM]: "ArrowPathIcon",
                [LOG_TYPES.INFO]: "InformationCircleIcon",
            };
            return iconMap[type] || "InformationCircleIcon";
        },
        getIconBgClass(entry) {
            const type = this.getLogType(entry);
            const classMap = {
                [LOG_TYPES.OPEN_SUCCESS]: "bg-emerald-100",
                [LOG_TYPES.CLOSE_SUCCESS]: "bg-blue-100",
                [LOG_TYPES.SENSOR_OPEN]: "bg-orange-100",
                [LOG_TYPES.SENSOR_CLOSE]: "bg-slate-100",
                [LOG_TYPES.ERROR]: "bg-red-100",
                [LOG_TYPES.POSTPONE]: "bg-amber-100",
                [LOG_TYPES.SCHEDULE]: "bg-indigo-100",
                [LOG_TYPES.SYSTEM]: "bg-purple-100",
                [LOG_TYPES.INFO]: "bg-gray-100",
            };
            return classMap[type] || "bg-gray-100";
        },
        getIconClass(entry) {
            const type = this.getLogType(entry);
            const classMap = {
                [LOG_TYPES.OPEN_SUCCESS]: "text-emerald-600",
                [LOG_TYPES.CLOSE_SUCCESS]: "text-blue-600",
                [LOG_TYPES.SENSOR_OPEN]: "text-orange-600",
                [LOG_TYPES.SENSOR_CLOSE]: "text-slate-600",
                [LOG_TYPES.ERROR]: "text-red-600",
                [LOG_TYPES.POSTPONE]: "text-amber-600",
                [LOG_TYPES.SCHEDULE]: "text-indigo-600",
                [LOG_TYPES.SYSTEM]: "text-purple-600",
                [LOG_TYPES.INFO]: "text-gray-600",
            };
            return classMap[type] || "text-gray-600";
        },
        getLabel(entry) {
            const type = this.getLogType(entry);
            const labelMap = {
                [LOG_TYPES.OPEN_SUCCESS]: "開",
                [LOG_TYPES.CLOSE_SUCCESS]: "閉",
                [LOG_TYPES.SENSOR_OPEN]: "照度",
                [LOG_TYPES.SENSOR_CLOSE]: "照度",
                [LOG_TYPES.ERROR]: "エラー",
                [LOG_TYPES.POSTPONE]: "見合わせ",
                [LOG_TYPES.SCHEDULE]: "スケジュール",
                [LOG_TYPES.SYSTEM]: "システム",
                [LOG_TYPES.INFO]: "情報",
            };
            return labelMap[type] || "情報";
        },
        formatMessage(message) {
            // 絵文字を除去してフォーマット
            return message
                .replace(/[😵📝📅🏃🔔🌅🌇]/gu, "")
                .trim()
                .replace(/\^2/g, "<sup>2</sup>")
                .replace(/\n/g, "<br/>")
                .replace(/\(by ([^)]+)\)/g, '<span class="whitespace-nowrap">(by $1)</span>');
        },
        updateLog: function () {
            axios
                .get(this.AppConfig["apiEndpoint"] + "log_view")
                .then((response) => {
                    this.log = response.data.data;
                    for (let entry in this.log) {
                        const date = dayjs(this.log[entry]["date"]);
                        this.log[entry]["date"] = date.format("M月D日(ddd) HH:mm");
                        this.log[entry]["fromNow"] = date.fromNow();
                    }
                })
                .catch(() => {
                    this.$root.$toast.open({
                        type: "error",
                        position: "top-right",
                        message: "ログデータの取得に失敗しました。",
                    });
                });
        },
        watchEvent: function () {
            this.eventSource = new EventSource(this.AppConfig["apiEndpoint"] + "event");
            this.eventSource.addEventListener("message", (e) => {
                if (e.data == "log") {
                    this.updateLog();
                }
            });
            this.eventSource.onerror = () => {
                if (this.eventSource.readyState == 2) {
                    this.eventSource.close();
                    setTimeout(this.watchEvent, 10000);
                }
            };
        },
        clear: function () {
            axios
                .get(this.AppConfig["apiEndpoint"] + "log_clear")
                .then((response) => {
                    if (response.data.result) {
                        this.$root.$toast.open({
                            type: "success",
                            position: "top-right",
                            message: "正常にクリアできました。",
                        });
                    } else {
                        this.$root.$toast.open({
                            type: "error",
                            position: "top-right",
                            message: "クリアに失敗しました。",
                        });
                    }
                })
                .catch(() => {
                    this.$root.$toast.open({
                        type: "error",
                        position: "top-right",
                        message: "クリアに失敗しました。",
                    });
                });
        },
    },
};
</script>

<style></style>
