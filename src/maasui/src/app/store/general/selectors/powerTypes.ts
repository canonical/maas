/**
 * Selector for power types.
 */

import { createSelector } from "@reduxjs/toolkit";

import { generateGeneralSelector } from "./utils";

const generalSelectors = generateGeneralSelector<"powerTypes">("powerTypes");

/**
 * Returns power drivers that can probe and enlist machines that it manages,
 * i.e. can be used with the `add_chassis` API method.
 * @param {RootState} state - The redux state.
 * @returns {PowerType[]} Chassis power types.
 */
const canProbe = createSelector([generalSelectors.get], (powerTypes) =>
  powerTypes.filter((type) => type.can_probe)
);

const powerTypes = {
  ...generalSelectors,
  canProbe,
};

export default powerTypes;
