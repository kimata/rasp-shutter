import { defineConfig } from "vite";
import { createHtmlPlugin } from "vite-plugin-html";
import vue from "@vitejs/plugin-vue";

// https://vitejs.dev/config/
export default defineConfig({
    base: "/rasp-shutter/",
    plugins: [
        createHtmlPlugin({
            inject: {
                data: {
                    buildTime: new Date().toUTCString(),
                },
            },
        }),
        vue(),
    ],
});
