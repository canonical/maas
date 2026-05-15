import { createSelector } from "reselect";

import type { RootState } from "@/app/store/root/types";
import { SpaceMeta } from "@/app/store/space/types";
import type { Space, SpaceState } from "@/app/store/space/types";
import { generateBaseSelectors } from "@/app/store/utils";

const searchFunction = (space: Space, term: string) =>
  space.name.includes(term);

const defaultSelectors = generateBaseSelectors<SpaceState, Space, SpaceMeta.PK>(
  SpaceMeta.MODEL,
  SpaceMeta.PK,
  searchFunction
);

/**
 * Get the space state object.
 * @param state - The redux state.
 * @returns The space state.
 */
const spaceState = (state: RootState): SpaceState => state[SpaceMeta.MODEL];

/**
 * Returns currently active space's id.
 * @param state - The redux state.
 * @returns Active space id.
 */
const activeID = createSelector(
  [spaceState],
  (spaceState) => spaceState.active
);

/**
 * Returns currently active space.
 * @param state - The redux state.
 * @returns Active space.
 */
const active = createSelector(
  [defaultSelectors.all, activeID],
  (spaces: Space[], activeID: Space[SpaceMeta.PK] | null) =>
    spaces.find((space) => activeID === space.id)
);

const selectors = {
  ...defaultSelectors,
  active,
  activeID,
  spaceState,
};

export default selectors;
