import { createSelector } from "@reduxjs/toolkit";

import type { Space } from "../space/types";

import fabricSelectors from "@/app/store/fabric/selectors";
import type { PodDetails } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import { SubnetMeta } from "@/app/store/subnet/types";
import type {
  Subnet,
  SubnetState,
  SubnetStatus,
} from "@/app/store/subnet/types";
import { generateBaseSelectors } from "@/app/store/utils";
import { isId } from "@/app/utils";

const searchFunction = (subnet: Subnet, term: string) =>
  subnet.name.includes(term);

const defaultSelectors = generateBaseSelectors<
  SubnetState,
  Subnet,
  SubnetMeta.PK
>(SubnetMeta.MODEL, SubnetMeta.PK, searchFunction);

/**
 * Get the subnet state object.
 * @param state - The redux state.
 * @returns The subnet state.
 */
const subnetState = (state: RootState): SubnetState => state[SubnetMeta.MODEL];

/**
 * Returns currently active subnet's id.
 * @param state - The redux state.
 * @returns Active subnet id.
 */
const activeID = createSelector(
  [subnetState],
  (subnetState) => subnetState.active
);

/**
 * Returns currently active subnet.
 * @param state - The redux state.
 * @returns Active subnet.
 */
const active = createSelector(
  [defaultSelectors.all, activeID],
  (subnets: Subnet[], activeID: Subnet[SubnetMeta.PK] | null) =>
    subnets.find((subnet) => activeID === subnet.id)
);

/**
 * Get subnets for given ids.
 * @param {RootState} state - The redux state.
 * @param {Pod} ids - A list of subnet ids
 * @returns {Subnet[]} The subnets for the given ids.
 */
const getByIds = createSelector(
  [
    defaultSelectors.all,
    (_state: RootState, ids: Subnet[SubnetMeta.PK][] | null) => ids,
  ],
  (subnets, ids = []) => {
    return subnets.filter(({ id }) => ids?.includes(id));
  }
);

/**
 * Get subnets for a given cidr.
 * @param state - The redux state.
 * @param cidr - The cidr to filter by.
 * @returns Subnets for a cidr.
 */
const getByCIDR = createSelector(
  [
    defaultSelectors.all,
    (_state: RootState, cidr: Subnet["cidr"] | null) => cidr,
  ],
  (subnets, cidr) => {
    if (!cidr) {
      return null;
    }
    return subnets.find((subnet) => subnet.cidr === cidr);
  }
);

/**
 * Get subnets that are available to a given pod.
 * @param {RootState} state - The redux state.
 * @param {Pod} pod - The pod to query.
 * @returns {Subnet[]} Subnets that are available to a given pod.
 */
const getByPod = createSelector(
  [defaultSelectors.all, (_state: RootState, pod: PodDetails) => pod],
  (subnets, pod) => {
    if (!pod) {
      return [];
    }
    return subnets.filter((subnet) =>
      pod.attached_vlans?.includes(subnet.vlan)
    );
  }
);

/**
 * Get subnets in a given space
 * @param {RootState} state - The redux state.
 * @param {Pod} VLANId - The id of the VLAN.
 * @returns {Subnet[]} Subnets for a Space.
 */
const getBySpace = createSelector(
  [
    defaultSelectors.all,
    (_state: RootState, spaceId: Space["id"] | null) => spaceId,
  ],
  (subnets, spaceId) => {
    if (!isId(spaceId)) {
      return [];
    }
    return subnets.filter((subnet) => subnet.space === spaceId);
  }
);

/**
 * Get subnets for a given VLAN.
 * @param {RootState} state - The redux state.
 * @param {Pod} VLANId - The id of the VLAN.
 * @returns {Subnet[]} Subnets for a VLAN.
 */
const getByVLAN = createSelector(
  [
    defaultSelectors.all,
    (_state: RootState, VLANId: Subnet["vlan"] | null) => VLANId,
  ],
  (subnets, VLANId) => {
    if (!isId(VLANId)) {
      return [];
    }
    return subnets.filter(({ vlan }) => vlan === VLANId);
  }
);

/**
 * Get subnets in a given fabric.
 * @param state - The redux state.
 * @param fabricId - The id of the fabric.
 * @returns Subnets in a fabric.
 */
const getByFabric = createSelector(
  [defaultSelectors.all, fabricSelectors.getById],
  (subnets, fabric) => {
    if (!fabric) {
      return [];
    }
    return subnets.filter((subnet) => fabric.vlan_ids.includes(subnet.vlan));
  }
);

/**
 * Get PXE-enabled subnets that are available to a given pod.
 * @param {RootState} state - The redux state.
 * @param {Pod} pod - The pod to query.
 * @returns {Subnet[]} PXE-enabled subnets that are available to a given pod.
 */
const getPxeEnabledByPod = createSelector(
  [defaultSelectors.all, (_state: RootState, pod: PodDetails) => pod],
  (subnets, pod) => {
    if (!pod) {
      return [];
    }
    return subnets.filter((subnet) => pod.boot_vlans?.includes(subnet.vlan));
  }
);

/**
 * Get the subnets statuses.
 * @param state - The redux state.
 * @returns The subnet statuses.
 */
const statuses = createSelector(
  [subnetState],
  (subnetState) => subnetState.statuses
);

/**
 * Get the statuses for a subnet.
 * @param state - The redux state.
 * @param id - A subnet's system id.
 * @returns The subnet's statuses
 */
const getStatusForSubnet = createSelector(
  [
    statuses,
    (
      _state: RootState,
      id: Subnet[SubnetMeta.PK] | null,
      status: keyof SubnetStatus
    ) => ({
      id,
      status,
    }),
  ],
  (allStatuses, { id, status }) =>
    isId(id) && id in allStatuses ? allStatuses[id][status] : false
);

/**
 * Returns the subnets which are being scanned.
 * @param state - The redux state.
 * @returns Subnets being scanned.
 */
const scanning = createSelector(
  [defaultSelectors.all, statuses],
  (subnets, statuses) =>
    subnets.filter(
      (subnet) => statuses[subnet[SubnetMeta.PK]]?.scanning || false
    )
);

/**
 * Select the event errors for all subnets.
 * @param state - The redux state.
 * @returns The event errors.
 */
const eventErrors = createSelector(
  [subnetState],
  (subnetState) => subnetState.eventErrors
);

/**
 * Select the event errors for a subnet or subnets.
 * @param ids - One or more subnet IDs.
 * @param event - A subnet action event.
 * @returns The event errors for the subnet(s).
 */
const eventErrorsForSubnets = createSelector(
  [
    eventErrors,
    (
      _state: RootState,
      ids: Subnet[SubnetMeta.PK] | Subnet[SubnetMeta.PK][] | null,
      event?: string | null
    ) => ({
      ids,
      event,
    }),
  ],
  (errors: SubnetState["eventErrors"][0][], { ids, event }) => {
    if (!errors || !ids) {
      return [];
    }
    // If a single id has been provided then turn into an array to operate over.
    const idArray = Array.isArray(ids) ? ids : [ids];
    return errors.reduce<SubnetState["eventErrors"][0][]>((matches, error) => {
      let match = false;
      const matchesId = !!error.id && idArray.includes(error.id);
      // If an event has been provided as `null` then filter for errors with
      // a null event.
      if (event || event === null) {
        match = matchesId && error.event === event;
      } else {
        match = matchesId;
      }
      if (match) {
        matches.push(error);
      }
      return matches;
    }, []);
  }
);

const selectors = {
  ...defaultSelectors,
  active,
  activeID,
  eventErrors,
  eventErrorsForSubnets,
  getByCIDR,
  getByFabric,
  getByIds,
  getByPod,
  getBySpace,
  getByVLAN,
  getPxeEnabledByPod,
  getStatusForSubnet,
  scanning,
  subnetState,
};

export default selectors;
