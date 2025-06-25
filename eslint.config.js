import globals from "globals";
import pluginJs from "@eslint/js";
import pluginVue from "eslint-plugin-vue";

export default [
    {
        files: ["**/*.{js,mjs,cjs,vue}"],
        ignores: ["dist/**", "node_modules/**", ".venv/**", "tests/evidence/**"],
    },
    { languageOptions: { globals: globals.browser } },
    pluginJs.configs.recommended,
    ...pluginVue.configs["flat/essential"],
    {
        languageOptions: {
            globals: {
                require: "readonly",
                module: "readonly",
                __dirname: "readonly",
                process: "readonly",
            },
            ecmaVersion: 2021, // ES2021をサポート
        },
    },
];
