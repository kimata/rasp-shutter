import globals from "globals";
import pluginJs from "@eslint/js";
import pluginVue from "eslint-plugin-vue";

export default [
    {
        ignores: ["dist/**", "node_modules/**", ".venv/**", "tests/evidence/**"],
    },
    {
        files: ["**/*.{js,mjs,cjs,vue}"],
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
            ecmaVersion: "latest",
        },
    },
];
