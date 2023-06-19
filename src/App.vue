<template>
    <div id="app">
        <app-header></app-header>
        <manual-control />
        <schedule-setting />
        <sensor-data />
        <app-log />
    </div>
</template>

<script>
import AppHeader from "./components/AppHeader";
import ManualControl from "./components/ManualControl";
import ScheduleSetting from "./components/ScheduleSetting";
import SensorData from "./components/SensorData";
import AppLog from "./components/AppLog";

export default {
    name: "app",
    components: {
        AppHeader,
        ManualControl,
        ScheduleSetting,
        SensorData,
        AppLog,
    },
    compatConfig: { MODE: 3 },
};
</script>

<style>
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

.btn-success {
    background: #28a745 !important;
}
</style>
