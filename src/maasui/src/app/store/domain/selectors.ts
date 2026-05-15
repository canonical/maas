import { createSelector } from "@reduxjs/toolkit";

import { DomainMeta } from "@/app/store/domain/types";
import type { Domain, DomainState } from "@/app/store/domain/types";
import type { RootState } from "@/app/store/root/types";
import { generateBaseSelectors } from "@/app/store/utils";

const searchFunction = (domain: Domain, term: string) =>
  domain.name.includes(term);

const defaultSelectors = generateBaseSelectors<
  DomainState,
  Domain,
  DomainMeta.PK
>(DomainMeta.MODEL, DomainMeta.PK, searchFunction);

/**
 * Get a domain by name.
 * @param state - The redux state.
 * @returns A domain.
 */
const getByName = createSelector(
  [
    defaultSelectors.all,
    (_state: RootState, name: Domain["name"] | null) => name,
  ],
  (domains, name) => domains.find((domain) => domain.name === name) || null
);

/**
 * Get the default domain.
 * @param state - The redux state.
 * @returns The default domain.
 */
const getDefault = createSelector(
  [defaultSelectors.all],
  (domains) => domains.find(({ is_default }) => is_default) || null
);

const selectors = {
  ...defaultSelectors,
  getByName,
  getDefault,
};

export default selectors;
