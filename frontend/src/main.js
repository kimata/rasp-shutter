import { createApp } from "vue";
import { ToastPlugin } from "vue-toast-notification";

import "./style.css";
import "vue-toast-notification/dist/theme-default.css";

import App from "./App.vue";

const app = createApp(App);
app.use(ToastPlugin);
app.mount("#app");
