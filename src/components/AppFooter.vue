<template>
    <div class="p-1 float-end text-end m-2">
        <small>
            <p class="text-muted m-0">
                <small>ビルド日時: {{ buildDate }} [{{ buildDateFrom }}]</small>
            </p>
        </small>
    </div>
</template>

<script>
import moment from "moment";
import "moment/locale/ja";

export default {
    name: "app-footer",
    data() {
        return {
            buildDate: moment(document.documentElement.dataset.buildDate).format("lll"),
            buildDateFrom: moment(document.documentElement.dataset.buildDate).fromNow(),
        };
    },
    compatConfig: { MODE: 3 },
};
</script>

<style></style>
