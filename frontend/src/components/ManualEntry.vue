<template>
    <div class="control-entry">
        <h3 class="mb-3">{{ this.name }}</h3>
        <div class="flex gap-3">
            <div class="w-1/2">
                <button
                    class="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded flex items-center justify-center gap-2"
                    @click="control('open')"
                    v-bind:data-testid="'open-' + index"
                >
                    <ArrowUpCircleIcon class="w-5 h-5" />
                    上げる
                </button>
            </div>

            <div class="w-1/2">
                <button
                    class="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded flex items-center justify-center gap-2"
                    @click="control('close')"
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
    methods: {
        control: function (mode) {
            axios
                .get(this.AppConfig["apiEndpoint"] + "shutter_ctrl", {
                    params: { cmd: 1, index: this.index, state: mode },
                })
                .then((response) => {
                    if (response.data.result) {
                        this.$root.$toast.open({
                            type: "success",
                            position: "top-right",
                            message: "正常に制御できました。",
                        });
                    } else {
                        this.$root.$toast.open({
                            type: "error",
                            position: "top-right",
                            message: "制御に失敗しました。",
                        });
                    }
                })
                .catch(() => {
                    this.$root.$toast.open({
                        type: "error",
                        position: "top-right",
                        message: "制御に失敗しました。",
                    });
                });
        },
    },
};
</script>

<style scoped></style>
