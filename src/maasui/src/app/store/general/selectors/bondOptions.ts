/**
 * Selector for all bond modes.
 */
import { createSelector } from "@reduxjs/toolkit";

import { generateGeneralSelector } from "./utils";

const generalSelectors = generateGeneralSelector<"bondOptions">("bondOptions");

/**
 * Returns a shallow/deduped array of LACP rates.
 */
const lacpRates = createSelector([generalSelectors.get], (options) =>
  options?.lacp_rates.map(([lacpRate]) => lacpRate)
);

/**
 * Returns a shallow/deduped array of modes.
 */
const modes = createSelector([generalSelectors.get], (options) =>
  options?.modes.map(([mode]) => mode)
);

/**
 * Returns a shallow/deduped array of XMIT hash policies.
 */
const xmitHashPolicies = createSelector([generalSelectors.get], (options) =>
  options?.xmit_hash_policies.map(([policy]) => policy)
);

const bondOptions = {
  ...generalSelectors,
  lacpRates,
  modes,
  xmitHashPolicies,
};
export default bondOptions;
