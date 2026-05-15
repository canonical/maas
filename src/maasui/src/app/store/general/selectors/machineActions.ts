import { createSelector } from "@reduxjs/toolkit";

import { generateGeneralSelector } from "./utils";

import type { MachineAction } from "@/app/store/general/types";
import type { RootState } from "@/app/store/root/types";

/**
 * Selector for all possible machine actions.
 */
const generalSelectors =
  generateGeneralSelector<"machineActions">("machineActions");

/**
 * Get a machine action by name.
 * @param {RootState} state - The redux state.
 * @param {MachineAction["name"]} name - The name of a machine action.
 * @returns {MachineAction} A machine action.
 */
const getByName = createSelector(
  [
    generalSelectors.get,
    (_state: RootState, name: MachineAction["name"]) => name,
  ],
  (actions: MachineAction[], name) =>
    actions.find((action: MachineAction) => action.name === name)
);

const machineActions = {
  ...generalSelectors,
  getByName,
};

export default machineActions;
