<template>
    <div class="container control-entry">
        <h3>{{ this.name }}</h3>
        <div class="row">
            <div class="col-6">
                <button class="btn btn-success w-100" @click="control('open')" v-bind:data-testid="'open-' + index">
                    <i class="bi bi-arrow-up-circle" />
                    上げる
                </button>
            </div>

            <div class="col-6">
                <button class="btn btn-success w-100" @click="control('close')" v-bind:data-testid="'close-' + index">
                    <i class="bi bi-arrow-down-circle" />
                    下げる
                </button>
            </div>
        </div>
    </div>
</template>

<script>
import axios from "axios";
import AppConfig from "../mixins/AppConfig.js";

export default {
    namex: "manual-entry",
    props: ["name", "index"],
    mixins: [AppConfig],
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
