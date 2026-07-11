import { defineConfig } from "vite";
import { createHtmlPlugin } from "vite-plugin-html";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";

// https://vitejs.dev/config/
export default defineConfig({
    base: "/rasp-shutter/",
    server: {
        // 開発サーバーでは API を Flask (port 5000) に中継する
        proxy: {
            "/rasp-shutter/api": "http://localhost:5000",
        },
    },
    plugins: [
        createHtmlPlugin({
            inject: {
                data: {
                    buildTime: new Date().toUTCString(),
                },
            },
        }),
        vue(),
        tailwindcss(),
    ],
});
