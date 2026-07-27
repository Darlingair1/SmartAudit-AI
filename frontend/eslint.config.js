import js from "@eslint/js";
import globals from "globals";
import pluginVue from "eslint-plugin-vue";

export default [
  { ignores: ["dist/**", "public/**"] },
  js.configs.recommended,
  ...pluginVue.configs["flat/recommended"],
  {
    files: ["**/*.{js,vue}"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: { "vue/multi-word-component-names": "off" },
  },
];
