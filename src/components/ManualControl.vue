<template>
    <div class="row mb-4">
        <div class="col-xl-6 offset-xl-3 col-lg-8 offset-lg-2 col-md-10 offset-md-1">
            <h2>手動</h2>
            <div class="container mt-4 mb-2">
                <div class="col-6">
                    <button class="btn btn-success" @click="control('open')" data-testid="open">
                        <i class="bi bi-arrow-up-circle" />
                        上げる
                    </button>
                </div>
                <div class="col-6">
                    <button class="btn btn-success" @click="control('close')" data-testid="close">
                        <i class="bi bi-arrow-down-circle" />
                        下げる
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import axios from "axios";
import AppConfig from "../mixins/AppConfig.js";

export default {
    name: "manual-control",
    mixins: [AppConfig],
    compatConfig: { MODE: 3 },
    methods: {
        control: function (mode) {
            axios
                .get(this.AppConfig["apiEndpoint"] + "shutter_ctrl", {
                    params: { cmd: 1, state: mode },
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
