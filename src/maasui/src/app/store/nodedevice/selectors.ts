import { createSelector } from "@reduxjs/toolkit";

import { NodeDeviceMeta } from "./types";
import type { NodeDevice, NodeDeviceState } from "./types";

import type { RootState } from "@/app/store/root/types";
import type { Node } from "@/app/store/types/node";
import { generateBaseSelectors } from "@/app/store/utils";

const defaultSelectors = generateBaseSelectors<
  NodeDeviceState,
  NodeDevice,
  NodeDeviceMeta.PK
>(NodeDeviceMeta.MODEL, NodeDeviceMeta.PK);

/**
 * Returns node devices by node id
 * @param state - Redux state
 * @returns node devices associated with a given node.
 */
const getByNodeId = createSelector(
  [defaultSelectors.all, (_: RootState, nodeId: Node["id"] | null) => nodeId],
  (nodeDevices, nodeId): NodeDevice[] =>
    nodeDevices.filter((nodeDevice) => nodeDevice.node_id === nodeId)
);

const nodeDevice = {
  ...defaultSelectors,
  getByNodeId,
};

export default nodeDevice;
