import { createSelector } from "reselect";

import { FabricMeta } from "@/app/store/fabric/types";
import type { Fabric, FabricState } from "@/app/store/fabric/types";
import type { RootState } from "@/app/store/root/types";
import { generateBaseSelectors } from "@/app/store/utils";

const searchFunction = (fabric: Fabric, term: string) =>
  fabric.name.includes(term);

const defaultSelectors = generateBaseSelectors<
  FabricState,
  Fabric,
  FabricMeta.PK
>(FabricMeta.MODEL, FabricMeta.PK, searchFunction);

/**
 * Get the fabric state object.
 * @param state - The redux state.
 * @returns The fabric state.
 */
const fabricState = (state: RootState): FabricState => state[FabricMeta.MODEL];

/**
 * Returns currently active fabric's id.
 * @param state - The redux state.
 * @returns Active fabric id.
 */
const activeID = createSelector(
  [fabricState],
  (fabricState) => fabricState.active
);

/**
 * Returns currently active fabric.
 * @param state - The redux state.
 * @returns Active fabric.
 */
const active = createSelector(
  [defaultSelectors.all, activeID],
  (fabrics: Fabric[], activeID: Fabric[FabricMeta.PK] | null) =>
    fabrics.find((fabric) => activeID === fabric.id)
);

const selectors = {
  ...defaultSelectors,
  active,
  activeID,
  fabricState,
};

export default selectors;
