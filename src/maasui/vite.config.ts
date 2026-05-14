/// <reference types="vitest" />
import react from "@vitejs/plugin-react-swc";
import * as path from "path";
import { defineConfig, loadEnv } from "vite";
import eslint from "vite-plugin-eslint";

const manualChunks = [
  "@canonical/react-components",
  "@canonical/maas-react-components",
  "@canonical/macaroon-bakery",
  "@/app/store/machine/slice",
];

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "./");

  return {
    envDir: "./",
    base: "/",
    css: {
      preprocessorOptions: {
        scss: {
          api: "modern",
          quietDeps: true,
          silenceDeprecations: ["import", "global-builtin"],
        },
      },
    },
    define: {
      "process.env": env,
    },
    build: {
      manifest: "asset-manifest.json",
      outDir: "build",
      rollupOptions: {
        output: {
          sanitizeFileName: false,
          // Creates an object with sanitized camel-cased module names as keys and original module names as values.
          // e.g.: { "canonicalReactComponents": ["@canonical/react-components"] }.
          manualChunks: manualChunks.reduce(
            (chunks: Record<string, string[]>, module) => {
              const sanitizedModule = module
                .replace(/(^|[-\/])(.)/g, (_, _separator, letter) =>
                  letter.toUpperCase()
                )
                .replace(/[^a-zA-Z0-9]/g, "")
                .replace(/^./, (firstChar) => firstChar.toLowerCase());
              chunks[sanitizedModule] = [module];
              return chunks;
            },
            {}
          ),
        },
      },
      sourcemap: true,
    },
    plugins: [react(), eslint()],
    server: { port: 8401, hmr: process.env.CI ? false : { port: 8402 } },
    resolve: {
      alias: { "@": path.resolve(__dirname, "src") },
    },
  };
});
