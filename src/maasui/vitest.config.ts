import { configDefaults, defineConfig } from "vitest/config";
import * as path from "path";

export default defineConfig({
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  css: {
    preprocessorOptions: {
      scss: {
        silenceDeprecations: ["legacy-js-api"],
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    exclude: [...configDefaults.exclude, "**/tests/**"],
    clearMocks: true,
    coverage: {
      // use instrumented coverage via istanbul instead of v8
      provider: "istanbul",
      reporter: [
        ["text"],
        ["html"],
        ["lcov"],
        ["cobertura", { file: "../.coverage/cobertura-coverage.xml" }],
      ],
    },
  },
});
