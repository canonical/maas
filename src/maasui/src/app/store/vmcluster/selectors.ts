import { createSelector } from "@reduxjs/toolkit";

import { generateBaseSelectors } from "../utils";

import { VMClusterMeta } from "./types";
import type { VMClusterState, VMCluster, VMClusterStatuses } from "./types";

import type { RootState } from "@/app/store/root/types";

const defaultSelectors = generateBaseSelectors<
  VMClusterState,
  VMCluster,
  VMClusterMeta.PK
>(VMClusterMeta.MODEL, VMClusterMeta.PK);

/**
 * Get the vmcluster state object.
 * @param state - The redux state.
 * @returns The vmcluster state.
 */
const vmclusterState = (state: RootState): VMClusterState =>
  state[VMClusterMeta.MODEL];

/**
 * Get the vmclusters statuses.
 * @param state - The redux state.
 * @returns The vmcluster statuses.
 */
const statuses = createSelector(
  [vmclusterState],
  (vmclusterState) => vmclusterState.statuses
);

/**
 * Get the vmclusters event errors that match an event.
 * @param state - The redux state.
 * @returns The vmcluster event errors for the given event.
 */
const status = createSelector(
  [
    statuses,
    (_state: RootState, statusName: keyof VMClusterStatuses) => statusName,
  ],
  (statuses, statusName) => statuses[statusName]
);

/**
 * Get the vmclusters event errors.
 * @param state - The redux state.
 * @returns The vmcluster event errors.
 */
const eventErrors = createSelector(
  [vmclusterState],
  (vmclusterState) => vmclusterState.eventErrors
);

/**
 * Get the vmclusters event errors that match an event.
 * @param state - The redux state.
 * @returns The vmcluster event errors for the given event.
 */
const eventError = createSelector(
  [eventErrors, (_state: RootState, eventName: string) => eventName],
  (eventErrors, eventName) =>
    eventErrors.filter((eventError) => eventError.event === eventName)
);

const selectors = {
  ...defaultSelectors,
  eventError,
  eventErrors,
  status,
  statuses,
};

export default selectors;
