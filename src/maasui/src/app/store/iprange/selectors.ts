import { createSelector } from "@reduxjs/toolkit";

import type { RootState } from "../root/types";

import { IPRangeMeta } from "@/app/store/iprange/types";
import type { IPRange, IPRangeState } from "@/app/store/iprange/types";
import { generateBaseSelectors } from "@/app/store/utils";
import { isId } from "@/app/utils";

const defaultSelectors = generateBaseSelectors<
  IPRangeState,
  IPRange,
  IPRangeMeta.PK
>(IPRangeMeta.MODEL, IPRangeMeta.PK);

/**
 * Finds IP ranges for a subnet.
 * @param state - The redux state.
 * @param id - A subnet's id.
 * @returns IP ranges for a subnet.
 */
const getBySubnet = createSelector(
  [
    defaultSelectors.all,
    (_state: RootState, id: IPRange["subnet"] | undefined) => id,
  ],
  (ipRanges, id) => {
    if (!isId(id)) {
      return [];
    }
    return ipRanges.filter(({ subnet }) => subnet === id);
  }
);

/**
 * Get IP ranges for a VLAN.
 * @param state - The redux state.
 * @param id - The id of the VLAN.
 * @returns IP ranges for a VLAN.
 */
const getByVLAN = createSelector(
  [
    defaultSelectors.all,
    (_state: RootState, id: IPRange["vlan"] | undefined) => id,
  ],
  (ipRanges, id) => {
    if (!isId(id)) {
      return [];
    }
    return ipRanges.filter(({ vlan }) => vlan === id);
  }
);

const selectors = {
  ...defaultSelectors,
  getBySubnet,
  getByVLAN,
};

export default selectors;
