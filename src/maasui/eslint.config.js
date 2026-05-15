import { fixupConfigRules, fixupPluginRules } from "@eslint/compat";
import { FlatCompat } from "@eslint/eslintrc";
import js from "@eslint/js";

import cypress from "eslint-plugin-cypress";
import noOnlyTests from "eslint-plugin-no-only-tests";
import prettier from "eslint-plugin-prettier";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import unusedImports from "eslint-plugin-unused-imports";

import path from "path";
import { fileURLToPath } from "url";

import tseslint from "typescript-eslint";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
  allConfig: js.configs.all,
});

export default tseslint.config(
  tseslint.configs.recommended,
  reactHooks.configs["recommended-latest"],
  ...fixupConfigRules(
    compat.extends(
      "plugin:prettier/recommended",
      "plugin:storybook/recommended"
    )
  ),
  {
    plugins: {
      "unused-imports": unusedImports,
      react,
      prettier: fixupPluginRules(prettier),
    },

    languageOptions: {
      globals: {
        usabilla_live: false,
      },

      ecmaVersion: 2018,
      sourceType: "module",

      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },

    settings: {
      react: {
        version: "detect",
      },

      "import/resolver": {
        typescript: true,
      },
    },

    rules: {
      "prettier/prettier": "error",
    },
  },
  ...fixupConfigRules(
    compat.extends(
      "prettier",
      "plugin:import/errors",
      "plugin:import/warnings",
      "plugin:import/typescript",
      "plugin:prettier/recommended"
    )
  ).map((config) => ({
    ...config,
    files: ["src/**/*.ts?(x)"],
  })),
  {
    files: ["src/**/*.ts?(x)"],
    ignores: ["src/app/apiclient/**/*.ts"],
    plugins: {
      "unused-imports": unusedImports,
      react,
    },

    languageOptions: {
      ecmaVersion: 2018,
      sourceType: "module",

      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },

    settings: {
      "import/resolver": {
        node: {
          paths: ["src"],
          extensions: [".js", ".jsx", ".ts", ".tsx"],
        },
      },

      react: {
        version: "detect",
      },
    },

    rules: {
      "prettier/prettier": "error",

      complexity: [
        "error",
        {
          max: 34,
        },
      ],

      "@typescript-eslint/no-unused-vars": "off",
      "unused-imports/no-unused-imports": "error",
      "@typescript-eslint/no-unused-expressions": [
        "error",
        {
          allowShortCircuit: true,
          allowTernary: true,
        },
      ],

      "unused-imports/no-unused-vars": [
        "warn",
        {
          vars: "all",
          varsIgnorePattern: "^_",
          args: "after-used",
          ignoreRestSiblings: true,
          argsIgnorePattern: "^_",
        },
      ],

      "@typescript-eslint/consistent-type-imports": 2,
      "import/namespace": "off",
      "import/no-named-as-default": 0,

      "import/order": [
        "error",
        {
          pathGroups: [
            {
              pattern: "react",
              group: "external",
              position: "before",
            },
            {
              pattern: "~/app",
              group: "internal",
            },
          ],

          pathGroupsExcludedImportTypes: ["react"],
          "newlines-between": "always",

          alphabetize: {
            order: "asc",
          },
        },
      ],

      "no-console": "warn",

      "react/forbid-component-props": [
        "error",
        {
          forbid: [
            {
              propName: "data-test",
              message: "Use `data-testid` instead of `data-test` attribute",
            },
          ],
        },
      ],

      "react/forbid-dom-props": [
        "error",
        {
          forbid: [
            {
              propName: "data-test",
              message: "Use `data-testid` instead of `data-test` attribute",
            },
          ],
        },
      ],

      "react/jsx-sort-props": "error",
    },
  },
  {
    files: ["src/**/*.js?(x)"],

    rules: {
      "no-unused-vars": 2,
    },
  },
  {
    files: ["src/**/*.tsx"],

    rules: {
      "react/no-multi-comp": ["off"],
    },
  },
  {
    files: ["src/app/**/*.ts?(x)"],

    languageOptions: {
      parserOptions: {
        project: "./tsconfig.json",
      },
    },

    // The commented-out rules below are checked for code quality by TiCS.
    // Currently, these rules have errors that are challenging to fix;
    // therefore, they should only be enabled after all corresponding errors
    // are resolved.
    rules: {
      "@typescript-eslint/array-type": "error",
      // "@typescript-eslint/class-methods-use-this": "error",
      "@typescript-eslint/consistent-indexed-object-style": "error",
      // "@typescript-eslint/consistent-return": "error",
      // "@typescript-eslint/consistent-type-definitions": "error",
      // "@typescript-eslint/consistent-type-exports": "error",
      "@typescript-eslint/dot-notation": "error",
      // "@typescript-eslint/explicit-function-return-type": "error",
      // "@typescript-eslint/explicit-member-accessibility": "error",
      // "@typescript-eslint/explicit-module-boundary-types": "error",
      // "@typescript-eslint/init-declarations": "error",
      // "@typescript-eslint/max-params": [
      //   "error",
      //   {
      //     max: 3,
      //   },
      // ],
      "@typescript-eslint/no-confusing-void-expression": "error",
      "@typescript-eslint/no-duplicate-type-constituents": "error",
      // "@typescript-eslint/no-dynamic-delete": "error",
      // "@typescript-eslint/no-empty-function": "error",
      "@typescript-eslint/no-explicit-any": "error",
      // "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-for-in-array": "error",
      "@typescript-eslint/no-import-type-side-effects": "error",
      "@typescript-eslint/no-inferrable-types": "error",
      // "@typescript-eslint/no-invalid-void-type": "error",
      // "@typescript-eslint/no-non-null-assertion": "error",
      // "@typescript-eslint/no-redeclare": "error",
      // "@typescript-eslint/no-redundant-type-constituents": "error",
      // "@typescript-eslint/no-shadow": "error",
      // "@typescript-eslint/no-unnecessary-boolean-literal-compare": "error",
      // "@typescript-eslint/no-unnecessary-condition": "error",
      "@typescript-eslint/no-unnecessary-type-arguments": "error",
      // "@typescript-eslint/no-unnecessary-type-assertion": "error",
      // "@typescript-eslint/no-unsafe-argument": "error",
      // "@typescript-eslint/no-unsafe-assignment": "error",
      // "@typescript-eslint/no-unsafe-call": "error",
      // "@typescript-eslint/no-unsafe-enum-comparison": "error",
      // "@typescript-eslint/no-unsafe-member-access": "error",
      // "@typescript-eslint/no-unsafe-return": "error",
      "@typescript-eslint/no-unused-expressions": "error",
      // "@typescript-eslint/no-use-before-define": "error",
      // "@typescript-eslint/non-nullable-type-assertion-style": "error",
      // "@typescript-eslint/prefer-destructuring": "error",
      // "@typescript-eslint/prefer-enum-initializers": "error",
      // "@typescript-eslint/prefer-find": "error",
      // "@typescript-eslint/prefer-for-of": "error",
      "@typescript-eslint/prefer-includes": "error",
      // "@typescript-eslint/prefer-literal-enum-member": "error",
      // "@typescript-eslint/prefer-nullish-coalescing": "error",
      // "@typescript-eslint/prefer-optional-chain": "error",
      // "@typescript-eslint/prefer-promise-reject-errors": "error",
      "@typescript-eslint/prefer-reduce-type-parameter": "error",
      "@typescript-eslint/prefer-regexp-exec": "error",
      // "@typescript-eslint/prefer-ts-expect-error": "error",
      // "@typescript-eslint/promise-function-async": "error",
      // "@typescript-eslint/require-array-sort-compare": "error",
      "@typescript-eslint/restrict-plus-operands": "error",
      // "@typescript-eslint/restrict-template-expressions": "error",
      "@typescript-eslint/sort-type-constituents": "error",
      // "@typescript-eslint/strict-boolean-expressions": "error",
      // "@typescript-eslint/switch-exhaustiveness-check": "error",
      "@typescript-eslint/use-unknown-in-catch-callback-variable": "error",
    },
  },
  {
    files: ["src/app/apiclient/**/*.[jt]s?(x)"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/ban-ts-comment": "off",
    },
  },
  ...compat.extends("plugin:testing-library/react").map((config) => ({
    ...config,
    files: ["src/**/*.test.[jt]s?(x)"],
  })),
  {
    files: ["src/**/*.test.[jt]s?(x)"],

    plugins: {
      "no-only-tests": noOnlyTests,
    },

    rules: {
      "no-only-tests/no-only-tests": "error",
      "testing-library/prefer-find-by": "off",
      "testing-library/prefer-explicit-assert": "error",

      "testing-library/prefer-user-event": [
        "error",
        {
          allowedMethods: ["change"],
        },
      ],

      "react/no-multi-comp": "off",
    },
  },
  ...fixupConfigRules(compat.extends("plugin:prettier/recommended")).map(
    (config) => ({
      ...config,
      files: ["cypress/**/*.spec.[jt]s?(x)", "cypress/support/*.ts"],
    })
  ),
  {
    files: ["cypress/**/*.spec.[jt]s?(x)", "cypress/support/*.ts"],

    plugins: {
      cypress: fixupPluginRules(cypress),
      "no-only-tests": noOnlyTests,
    },

    rules: {
      ...cypress.configs.recommended.rules,
      "no-only-tests/no-only-tests": "error",
      "cypress/no-force": "off",
      "prettier/prettier": "error",
      "@typescript-eslint/no-unused-expressions": [
        "error",
        {
          allowShortCircuit: true,
          allowTernary: true,
        },
      ],
      "@typescript-eslint/no-namespace": ["error", { allowDeclarations: true }],
    },
  },
  ...compat.extends("plugin:playwright/recommended").map((config) => ({
    ...config,
    files: ["tests/**/*.[jt]s?(x)"],
  })),
  {
    files: ["tests/**/*.[jt]s?(x)"],

    plugins: {
      "no-only-tests": noOnlyTests,
    },

    rules: {
      "playwright/no-force-option": "off",
      "no-only-tests/no-only-tests": "error",
      "prettier/prettier": "error",
    },
  }
);
