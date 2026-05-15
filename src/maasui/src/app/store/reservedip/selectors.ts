import { createSelector } from "@reduxjs/toolkit";

import type { RootState } from "../root/types";

import type { ReservedIp, ReservedIpState } from "./types";
import { ReservedIpMeta } from "./types/enum";

import { generateBaseSelectors } from "@/app/store/utils";
import { isId } from "@/app/utils";

const defaultSelectors = generateBaseSelectors<
  ReservedIpState,
  ReservedIp,
  ReservedIpMeta.PK
>(ReservedIpMeta.MODEL, ReservedIpMeta.PK);

const getBySubnet = createSelector(
  [
    defaultSelectors.all,
    (_state: RootState, id: ReservedIp["subnet"] | undefined) => id,
  ],
  (reservedIps, id) => {
    if (!isId(id)) {
      return [];
    }
    return reservedIps.filter(({ subnet }) => subnet === id);
  }
);

const selectors = {
  ...defaultSelectors,
  getBySubnet,
};

export default selectors;
