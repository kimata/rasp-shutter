<template>
    <div class="row mb-4">
        <div class="col-xl-6 offset-xl-3 col-lg-8 offset-lg-2 col-md-10 offset-md-1">
            <h2>実行ログ</h2>
            <div class="container log">
                <p v-if="log.length == 0">ログがありません。</p>
                <div
                    v-else
                    class="row"
                    v-for="(entry, index) in log.slice((page - 1) * pageSize, page * pageSize)"
                    :key="index"
                >
                    <div class="col-12 font-weight-bold">
                        {{ entry.date }}
                        <small class="text-muted">({{ entry.fromNow }})</small>
                    </div>
                    <div
                        class="col-12 log-message mb-1"
                        v-html="entry.message.replace(/\^2/g, '<sup>2</sup>').replace(/\n/g, '<br/>')"
                    ></div>
                    <hr class="dashed" />
                </div>
                <b-pagination
                    v-model="page"
                    :total-rows="log.length"
                    :per-page="pageSize"
                    class="justify-content-center"
                ></b-pagination>
            </div>
            <div class="container mt-4 mb-2">
                <button type="button" class="btn btn-success col-12" @click="clear()" data-testid="clear">
                    <i class="bi bi-file-earmark-x" />
                    クリア
                </button>
            </div>
        </div>
    </div>
</template>

<script>
import axios from "axios";

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
    data() {
        return {
            pageSize: 10,
            page: 1,
            log: [],
            eventSource: null,
        };
    },
    compatConfig: { MODE: 3 },
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

<style>
hr.dashed {
    border-top: 2px dashed #999;
}
.page-link {
    color: #28a745 !important;
}
.page-item.active .page-link {
    background-color: #28a745 !important;
    border-color: #28a745 !important;
    color: #ffffff !important;
}
</style>
