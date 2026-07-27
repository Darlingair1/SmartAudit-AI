import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.js"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      include: ["src/api/**/*.js", "src/utils/**/*.js", "src/router/**/*.js"],
      exclude: ["**/*.test.js"],
      thresholds: { lines: 60, functions: 60, branches: 70, statements: 60 }
    }
  }
});
