<template>
    <div class="row mb-4 mt-4">
        <div class="col-xl-6 offset-xl-3 col-lg-8 offset-lg-2 col-md-10 offset-md-1">
            <h2>手動</h2>
            <div class="schedule-setting">
                <p v-if="shutter_list.length == 0">シャッター一覧を読み込み中...</p>
                <div v-else class="row">
                    <div v-for="(name, index) in shutter_list" :key="index" class="col-lg-6 col-md-12">
                        <ManualEntry v-bind:name="name" v-bind:index="index" />
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import ManualEntry from "./ManualEntry.vue";
import axios from "axios";
import AppConfig from "../mixins/AppConfig.js";

export default {
    name: "manual-control",
    mixins: [AppConfig],
    data() {
        return {
            shutter_list: [],
        };
    },
    components: {
        ManualEntry,
    },
    compatConfig: { MODE: 3 },
    created() {
        this.updateShutterList();
    },
    methods: {
        updateShutterList: function () {
            axios
                .get(this.AppConfig["apiEndpoint"] + "shutter_list")
                .then((response) => {
                    this.shutter_list = response.data;
                })
                .catch(() => {
                    this.$root.$toast.open({
                        type: "error",
                        position: "top-right",
                        message: "シャッター一覧の取得に失敗しました。",
                    });
                });
        },
    },
};
</script>

<style scoped></style>
