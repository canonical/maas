import { addCucumberPreprocessorPlugin } from "@badeball/cypress-cucumber-preprocessor";
import { createEsbuildPlugin } from "@badeball/cypress-cucumber-preprocessor/esbuild";
import createBundler from "@bahmutov/cypress-esbuild-preprocessor";
import { defineConfig } from "cypress";

export default defineConfig({
  defaultCommandTimeout: 10000,
  e2e: {
    // block analytics
    blockHosts: [
      "www.googletagmanager.com",
      "www.google-analytics.com",
      "sentry.is.canonical.com",
    ],

    // We've imported your old cypress plugins here.
    // You may want to clean this up later by importing these.
    // Here we use any type as Cypress’s on function supports many different event types, but its TypeScript definitions
    // only fully cover "task", so strictly typing on causes errors for other events like "file:preprocessor"
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    async setupNodeEvents(on: any, config) {
      await addCucumberPreprocessorPlugin(on, config);
      on("task", {
        log(args: unknown) {
          console.log(args);

          return null;
        },
        table(message: unknown) {
          console.table(message);

          return null;
        },
      });
      const jsBundler = createBundler({});

      on("file:preprocessor", (file: Cypress.FileObject) => {
        if (file.filePath.endsWith(".feature")) {
          return createBundler({
            plugins: [createEsbuildPlugin(config)],
          })(file);
        }

        if (
          file.filePath.match(/\.(js|ts|jsx|tsx)$/) &&
          !file.filePath.endsWith(".steps.ts")
        ) {
          return jsBundler(file);
        }

        return undefined;
      });
      return config;
    },
    baseUrl: "http://0.0.0.0:8400",
    specPattern: [
      "cypress/e2e/**/*.{js,jsx,ts,tsx}",
      "cypress/e2e/**/*.feature",
    ],
    viewportHeight: 1300,
    viewportWidth: 1440,
  },
  env: {
    BASENAME: "/MAAS",
    VITE_BASENAME: "/r",
    nonAdminPassword: "test",
    nonAdminUsername: "user",
    password: "test",
    skipA11yFailures: false,
    username: "admin",
    KEYCLOAK_URL: "http://localhost",
    KEYCLOAK_PORT: "8080",
  },
  projectId: "gp2cox",
  retries: {
    runMode: 2,
    openMode: 0,
  },
  video: false,
});
