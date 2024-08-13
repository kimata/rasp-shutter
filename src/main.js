import { createApp } from "vue";
import { createBootstrap } from "bootstrap-vue-next";
import { ToastPlugin } from "vue-toast-notification";

import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-vue-next/dist/bootstrap-vue-next.css";
import "bootstrap-icons/font/bootstrap-icons.min.css";
import "vue-toast-notification/dist/theme-bootstrap.css";

import App from "./App.vue";

const app = createApp(App);
app.use(ToastPlugin);
app.use(createBootstrap());
app.mount("#app");
