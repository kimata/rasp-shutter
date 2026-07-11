<template>
    <div class="control-entry">
        <h3 class="mb-3">{{ this.name }}</h3>
        <div class="flex gap-3">
            <div class="w-1/2">
                <button
                    class="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded flex items-center justify-center gap-2"
                    @click="control('open')"
                    v-bind:disabled="controlling"
                    v-bind:data-testid="'open-' + index"
                >
                    <ArrowUpCircleIcon class="w-5 h-5" />
                    上げる
                </button>
            </div>

            <div class="w-1/2">
                <button
                    class="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded flex items-center justify-center gap-2"
                    @click="control('close')"
                    v-bind:disabled="controlling"
                    v-bind:data-testid="'close-' + index"
                >
                    <ArrowDownCircleIcon class="w-5 h-5" />
                    下げる
                </button>
            </div>
        </div>
    </div>
</template>

<script>
import axios from "axios";
import { ArrowUpCircleIcon, ArrowDownCircleIcon } from "@heroicons/vue/24/outline";
import AppConfig from "../mixins/AppConfig.js";

export default {
    name: "manual-entry",
    props: ["name", "index"],
    mixins: [AppConfig],
    components: {
        ArrowUpCircleIcon,
        ArrowDownCircleIcon,
    },
    compatConfig: { MODE: 3 },
    data() {
        return {
            controlling: false,
        };
    },
    methods: {
        control: function (mode) {
            this.controlling = true;
            axios
                .post(this.AppConfig["apiEndpoint"] + "shutter_ctrl", null, {
                    params: { cmd: 1, index: this.index, state: mode },
                })
                .then((response) => {
                    const postponed = response.data.postponed || [];
                    if (response.data.result !== "success") {
                        this.$root.$toast.open({
                            type: "error",
                            position: "top-right",
                            message: "制御に失敗しました。",
                        });
                    } else if (postponed.includes(this.name)) {
                        this.$root.$toast.open({
                            type: "warning",
                            position: "top-right",
                            message: "直前に操作しているため、見合わせました。",
                        });
                    } else {
                        this.$root.$toast.open({
                            type: "success",
                            position: "top-right",
                            message: "正常に制御できました。",
                        });
                    }
                })
                .catch(() => {
                    this.$root.$toast.open({
                        type: "error",
                        position: "top-right",
                        message: "制御に失敗しました。",
                    });
                })
                .finally(() => {
                    this.controlling = false;
                });
        },
    },
};
</script>

<style scoped></style>
