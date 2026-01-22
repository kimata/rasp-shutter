<template>
    <div id="app">
        <div class="max-w-4xl mx-auto px-4">
            <app-header></app-header>
            <manual-control />
            <schedule-setting />
            <sensor-data />
            <app-log />
        </div>
        <app-footer />
    </div>
</template>

<script>
import AppHeader from "./components/AppHeader.vue";
import ManualControl from "./components/ManualControl.vue";
import ScheduleSetting from "./components/ScheduleSetting.vue";
import SensorData from "./components/SensorData.vue";
import AppLog from "./components/AppLog.vue";
import AppFooter from "./components/AppFooter.vue";

export default {
    name: "app",
    components: {
        AppHeader,
        ManualControl,
        ScheduleSetting,
        SensorData,
        AppLog,
        AppFooter,
    },
    compatConfig: { MODE: 3 },
};
</script>

<style>
@import url("https://fonts.googleapis.com/css2?family=BIZ+UDPGothic:wght@400;700&display=swap");

body {
    font-family: "BIZ UDPGothic", sans-serif !important;
}

h2 {
    border-bottom: solid 3px #cde6b8;
    position: relative;
}

h2:after {
    position: absolute;
    content: " ";
    display: block;
    border-bottom: solid 3px #82b956;
    bottom: -3px;
    width: 20%;
}

h3 {
    font-size: 1.1rem !important;
    margin-top: 1em !important;
}

.v-toast {
    opacity: 0.7;
}

input[type="checkbox"] {
    accent-color: #23903c;
}
</style>
