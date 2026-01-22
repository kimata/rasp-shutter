<template>
    <div class="mb-4">
        <h2>実行ログ</h2>
        <div class="log mt-4">
            <p v-if="log.length == 0" class="text-gray-500 text-center py-4">ログがありません。</p>
            <div v-else class="space-y-3">
                <div
                    v-for="(entry, index) in log.slice((page - 1) * pageSize, page * pageSize)"
                    :key="index"
                    class="bg-gray-50 border border-gray-200 rounded-lg p-3"
                >
                    <div class="flex items-center gap-2 text-sm text-gray-600 mb-2">
                        <span class="font-medium text-gray-800">{{ entry.date }}</span>
                        <span class="text-gray-400">|</span>
                        <span class="text-gray-500">{{ entry.fromNow }}</span>
                    </div>
                    <div
                        class="log-message text-gray-700"
                        v-html="entry.message.replace(/\^2/g, '<sup>2</sup>').replace(/\n/g, '<br/>')"
                    ></div>
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
        <div class="mt-4 mb-2">
            <button
                type="button"
                class="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded flex items-center justify-center gap-2"
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
import { XCircleIcon } from "@heroicons/vue/24/outline";

import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import localizedFormat from "dayjs/plugin/localizedFormat";

dayjs.locale("ja");
dayjs.extend(relativeTime);
dayjs.extend(localizedFormat);

import AppConfig from "../mixins/AppConfig.js";

export default {
    name: "app-log",
    mixins: [AppConfig],
    components: {
        XCircleIcon,
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
