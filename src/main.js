import Vue from "vue";
import { createApp } from "vue";
import App from "./App.vue";

import BootstrapVueNext from "bootstrap-vue-next";

import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-vue-next/dist/bootstrap-vue-next.css";

import "bootstrap-icons/font/bootstrap-icons.min.css";

import ToastPlugin from "vue-toast-notification";
import "vue-toast-notification/dist/theme-bootstrap.css";

Vue.use(BootstrapVueNext);

const app = createApp(App);
app.use(ToastPlugin);
app.mount("#app");
