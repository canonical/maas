import { createSelector } from "@reduxjs/toolkit";

import type { RootState } from "@/app/store/root/types";
import { ScriptMeta, ScriptType } from "@/app/store/script/types";
import type { Script, ScriptState } from "@/app/store/script/types";
import { generateBaseSelectors } from "@/app/store/utils";

type ScriptTypeName = keyof typeof ScriptType;

const defaultSelectors = generateBaseSelectors<
  ScriptState,
  Script,
  ScriptMeta.PK
>(ScriptMeta.MODEL, ScriptMeta.PK);

/**
 * Returns true if scripts have errors
 * @param {RootState} state - Redux state
 * @returns {Boolean} have errors
 */
const hasErrors = createSelector([defaultSelectors.errors], (errors) =>
  typeof errors === "object" && errors !== null
    ? Object.entries(errors).length > 0
    : !!errors
);

/**
 * Returns all commissioning scripts
 * @param {RootState} state - Redux state
 * @returns []} Commissioning scripts
 */
const commissioning = createSelector(
  [defaultSelectors.all],
  (scriptItems: Script[]) =>
    scriptItems.filter(
      (item: Script) => item.script_type === ScriptType.COMMISSIONING
    )
);

/**
 * Returns all preselected commissioning scripts
 * @param {RootState} state - Redux state
 * @returns scripts - Commissioning scripts
 *
 */
const preselectedCommissioning = createSelector(
  [commissioning],
  (commissioningItems: Script[]): Script[] =>
    commissioningItems.filter((item) => !item.tags.includes("noauto"))
);

/**
 * Returns all testing scripts
 * @param {RootState} state - Redux state
 * @returns {Script[]} Testing scripts
 */
const testing = createSelector(
  [defaultSelectors.all],
  (scriptItems: Script[]) =>
    scriptItems.filter(
      (item: Script) => item.script_type === ScriptType.TESTING
    )
);

/**
 * Returns all default testing scripts
 * @param {RootState} state - Redux state
 * @returns scripts - Testing scripts
 *
 */
const defaultTesting = createSelector(
  [testing],
  (testingItems: Script[]): Script[] =>
    testingItems.filter(
      (item) => item.default === true && !item.tags.includes("noauto")
    )
);

/**
 * Returns testing scripts that contain a URL parameter
 * @param {RootState} state - Redux state
 * @returns {Script[]} Testing scripts
 */
const testingWithUrl = createSelector([testing], (testScripts) =>
  testScripts.filter((script: Script) =>
    Object.keys(script.parameters).some((key) => key === "url")
  )
);

/**
 * Get scripts that match a term.
 * @param {RootState} state - The redux state.
 * @param term - The term to match against.
 * @param type - The type of script.
 * @returns A filtered list of scripts.
 */
const search = createSelector(
  [
    defaultSelectors.all,
    (_state: RootState, term: string, type: string) => ({ term, type }),
  ],
  (scriptItems: Script[], { term, type }): Script[] => {
    const scripts = scriptItems.filter(
      (item: Script) =>
        item.script_type === ScriptType[type.toUpperCase() as ScriptTypeName]
    );
    if (term) {
      return scripts.filter(
        (item: Script) =>
          item.name.includes(term) || item.description.includes(term)
      );
    }
    return scripts;
  }
);

const scripts = {
  ...defaultSelectors,
  commissioning,
  preselectedCommissioning,
  hasErrors,
  search,
  testing,
  defaultTesting,
  testingWithUrl,
};

export default scripts;
