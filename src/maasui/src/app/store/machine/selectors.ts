import type { Selector } from "@reduxjs/toolkit";
import { createSelector } from "@reduxjs/toolkit";
import { createCachedSelector } from "re-reselect";

import { ACTIONS } from "@/app/store/machine/constants";
import type {
  Machine,
  MachineState,
  MachineStateCount,
  MachineStatus,
  MachineStatuses,
  MachineStateListGroup,
  MachineStateList,
} from "@/app/store/machine/types";
import { FilterGroupKey, MachineMeta } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import type { NetworkInterface } from "@/app/store/types/node";
import {
  generateBaseSelectors,
  getInterfaceById as getInterfaceByIdUtil,
} from "@/app/store/utils";
import { simpleSortByKey } from "@/app/utils";

const defaultSelectors = generateBaseSelectors<
  MachineState,
  Machine,
  MachineMeta.PK
>(MachineMeta.MODEL, MachineMeta.PK);

const machineState = (state: RootState): MachineState =>
  state[MachineMeta.MODEL];

/**
 * Returns currently active machine's system_id.
 * @param {RootState} state - The redux state.
 * @returns {Machine["system_id"]} Active machine system_id.
 */
const activeID = (state: RootState): Machine[MachineMeta.PK] | null =>
  state.machine.active;

/**
 * Returns all machine statuses.
 * @param {RootState} state - The redux state.
 * @returns {MachineStatuses} A list of all statuses.
 */
const statuses = (state: RootState): MachineStatuses => state.machine.statuses;

const statusKeys = <T extends object>(statuses: T): (keyof T)[] =>
  Object.keys(statuses) as (keyof T)[];

/**
 * Returns IDs of machines that are currently being processed.
 * @param {RootState} state - The redux state.
 * @returns {Machine["system_id"][]} List of machines being processed.
 */
const processing = (state: RootState): Machine[MachineMeta.PK][] =>
  Object.keys(state.machine.statuses).filter((machineID) =>
    statusKeys(state.machine.statuses[machineID]).some(
      (status) => state.machine.statuses[machineID][status] === true
    )
  );

export const statusSelectors: Record<
  string,
  Selector<RootState, Machine[]>
> = {};

// Create a selector for each machine status.
ACTIONS.forEach(({ status }) => {
  statusSelectors[status] = createSelector(
    [defaultSelectors.all, statuses],
    (machines: Machine[], statuses: MachineStatuses) =>
      machines.filter(({ system_id }) => statuses[system_id][status])
  );
});

/**
 * Returns a machine's action details by callId
 */
const getActionState = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState: MachineState, callId) =>
    callId && callId in machineState.actions
      ? machineState.actions[callId]
      : null
);

/**
 * Get the machines that are either tagging or untagging.
 * @param state - The redux state.
 * @returns Machines that are either tagging or untagging.
 */
const updatingTags = createSelector(
  [defaultSelectors.all, statuses],
  (machines: Machine[], statuses: MachineStatuses) =>
    machines.filter(
      ({ system_id }) =>
        statuses[system_id]?.tagging || statuses[system_id]?.untagging
    )
);

/**
 * Get the statuses for a machine.
 * @param state - The redux state.
 * @param id - A machine's system id.
 * @returns The machine's statuses
 */
const getStatuses = createSelector(
  [statuses, (_state: RootState, id: Machine[MachineMeta.PK]) => id],
  (allStatuses, id) => allStatuses[id]
);

/**
 * Get a status for a machine.
 * @param state - The redux state.
 * @param id - A machine's system id.
 * @returns The machine's statuses
 */
const getStatusForMachine = createSelector(
  [
    statuses,
    (
      _state: RootState,
      id: Machine[MachineMeta.PK],
      status: keyof MachineStatus
    ) => ({
      id,
      status,
    }),
  ],
  (allStatuses, { id, status }) => allStatuses[id][status]
);

/**
 * Returns currently active machine.
 * @param {RootState} state - The redux state.
 * @returns {Machine} Active machine.
 */
const active = createSelector(
  [defaultSelectors.all, activeID],
  (machines: Machine[], activeID: Machine[MachineMeta.PK] | null) =>
    machines.find((machine) => activeID === machine.system_id)
);

/**
 * Returns selected machines.
 * @param {RootState} state - The redux state.
 * @returns {Machine[]} Selected machines.
 */
const selected = createSelector([machineState], ({ selected }) => selected);

/**
 * Select the event errors for all machines.
 * @param state - The redux state.
 * @returns The event errors.
 */
const eventErrors = (state: RootState): MachineState["eventErrors"] =>
  state.machine.eventErrors;

/**
 * Select the event errors for a machine or machines.
 * @param ids - A machine's system ID or array of IDs.
 * @param event - A machine action event.
 * @returns The event errors for the machine.
 */
const eventErrorsForIds = createSelector(
  [
    eventErrors,
    (
      _state: RootState,
      ids: Machine[MachineMeta.PK] | Machine[MachineMeta.PK][],
      event?: string[] | string | null
    ) => ({
      ids,
      event,
    }),
  ],
  (errors: MachineState["eventErrors"][0][], { ids, event }) => {
    if (!errors || !ids) {
      return [];
    }
    // If a single id has been provided then turn into an array to operate over.
    const idArray = Array.isArray(ids) ? ids : [ids];
    return errors.reduce<MachineState["eventErrors"][0][]>((matches, error) => {
      let match = false;
      const matchesId = !!error.id
        ? !!error.id && idArray.includes(error.id)
        : !!error.callId && idArray.includes(error.callId);
      // If an event has been provided as `null` then filter for errors with
      // a null event.
      if (event || event === null) {
        const eventArray = Array.isArray(event) ? event : [event];
        const matchesEvent = eventArray.some((e) => error.event === e);
        match = matchesId && matchesEvent;
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

/**
 * Get an interface by id.
 * @param state - The redux state.
 * @param machineId - The id of the machine the interface belongs to.
 * @param interfaceId - The id the interface.
 * @returns A network interface.
 */
const getInterfaceById = createSelector(
  [
    defaultSelectors.all,
    (
      _state: RootState,
      machineId: Machine[MachineMeta.PK],
      interfaceId?: NetworkInterface["id"] | null,
      linkId?: NetworkInterface["id"] | null
    ) => ({
      interfaceId,
      linkId,
      machineId,
    }),
  ],
  (items: Machine[], { linkId, interfaceId, machineId }) => {
    const machine = items.find(({ system_id }) => system_id === machineId);
    if (!isMachineDetails(machine)) {
      return null;
    }
    return getInterfaceByIdUtil(machine, interfaceId, linkId);
  }
);

/**
 * Get the machines with a provided status code.
 * @param state - The redux state.
 * @param statusCode - A status code to filter by.
 * @returns The machines with a status code.
 */
const getByStatusCode = createSelector(
  [
    defaultSelectors.all,
    (_state: RootState, statusCode: Machine["status_code"]) => statusCode,
  ],
  (machines, statusCode) =>
    machines.filter(({ status_code }) => status_code === statusCode)
);

const getCount = (
  machine: MachineState,
  callId: string | null | undefined
): MachineStateCount | null =>
  callId && callId in machine.counts ? machine.counts[callId] : null;

const count = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => getCount(machineState, callId)?.count
);

const countLoaded = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => !!getCount(machineState, callId)?.loaded
);

const countLoading = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => !!getCount(machineState, callId)?.loading
);

const getDetails = (
  machineState: MachineState,
  callId: string | null | undefined
) =>
  callId && callId in machineState.details
    ? machineState.details[callId]
    : null;

/**
 * Get the loaded state for a details request.
 * @param state - The redux state.
 * @param callId - A details request id.
 * @returns Whether the details are loaded.
 */
const detailsLoaded = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => getDetails(machineState, callId)?.loaded
);

/**
 * Get the loading state for a details request.
 * @param state - The redux state.
 * @param callId - A details request id.
 * @returns Whether the details are loading.
 */
const detailsLoading = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => getDetails(machineState, callId)?.loading
);

/**
 * Get the machine filters.
 * @param state - The redux state.
 * @returns The machine filters.
 */
const filters = createSelector(
  [machineState],
  (machineState) => machineState.filters
);

/**
 * Get the loaded state for the machine filters.
 * @param state - The redux state.
 * @returns The machine filters loaded state.
 */
const filtersLoaded = createSelector(
  [machineState],
  (machineState) => machineState.filtersLoaded
);

/**
 * Get the loading state for the machine filters.
 * @param state - The redux state.
 * @returns The machine filters loading state.
 */
const filtersLoading = createSelector(
  [machineState],
  (machineState) => machineState.filtersLoading
);

const getFilterGroup = (
  machineState: MachineState,
  groupKey: FilterGroupKey | null | undefined
) =>
  groupKey ? machineState.filters?.find(({ key }) => key === groupKey) : null;

/**
 * Get the options for a filter group.
 * @param state - The redux state.
 * @param groupKey - A filter group key.
 * @returns The filter group options.
 */
const filterOptions = createSelector(
  [
    machineState,
    (_state: RootState, groupKey: FilterGroupKey | null | undefined) =>
      groupKey,
  ],
  (machineState, groupKey) => {
    const filterOptions = [
      ...(getFilterGroup(machineState, groupKey)?.options ?? []),
    ].sort(simpleSortByKey("label"));

    if (groupKey !== FilterGroupKey.Workloads) {
      return filterOptions;
    } else {
      const filterKeys = filterOptions.map((filter) => {
        return filter.key.toString().split(":")[0];
      });

      // Find the count of each workload annotation key
      const counts = filterKeys.reduce(
        (result: { key: string; count: number }[], currentFilterKey) => {
          const existingFilter = result.find(
            (filter) => filter.key === currentFilterKey
          );

          if (existingFilter) {
            existingFilter.count++;
          } else {
            result.push({ key: currentFilterKey, count: 1 });
          }

          return result;
        },
        []
      );

      // Turn array of keys and counts into valid filter options
      return counts.map((filterCount) => ({
        key: filterCount.key,
        label: `${filterCount.key} (${filterCount.count})`,
      }));
    }
  }
);

/**
 * Get the loaded state for a filter group.
 * @param state - The redux state.
 * @param groupKey - A filter group key.
 * @returns The filter group loaded state.
 */
const filterOptionsLoaded = createSelector(
  [
    machineState,
    (_state: RootState, groupKey: FilterGroupKey | null | undefined) =>
      groupKey,
  ],
  (machineState, groupKey) => getFilterGroup(machineState, groupKey)?.loaded
);

/**
 * Get the loading state for a filter group.
 * @param state - The redux state.
 * @param groupKey - A filter group key.
 * @returns The filter group loading state.
 */
const filterOptionsLoading = createSelector(
  [
    machineState,
    (_state: RootState, groupKey: FilterGroupKey | null | undefined) =>
      groupKey,
  ],
  (machineState, groupKey) => getFilterGroup(machineState, groupKey)?.loading
);

const getList = (
  machineState: MachineState,
  callId: string | null | undefined
): MachineStateList | null =>
  callId && callId in machineState.lists ? machineState.lists[callId] : null;

/**
 * Get the errors for a machine list request with a given callId
 */
const listErrors = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => getList(machineState, callId)?.errors || null
);

/**
 * Get the count for a machine list request with a given callId.
 */
const listCount = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => getList(machineState, callId)?.count ?? null
);

/**
 * Get the total page count for a machine list request with a given callId.
 */
const listTotalPages = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => getList(machineState, callId)?.num_pages ?? null
);

/**
 * Get the stale value for a machine count request with a given callId
 */
const countStale = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => getCount(machineState, callId)?.stale ?? null
);

/**
 * Get the stale value for a machine list request with a given callId
 */
const listStale = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => getList(machineState, callId)?.stale ?? null
);

/**
 * Get a group in a machine list request with a given callId.
 */
const listGroup = createSelector(
  [
    machineState,
    (
      _state: RootState,
      callId: string | null | undefined,
      name: MachineStateListGroup["name"] | null | undefined
    ) => ({
      callId,
      name,
    }),
  ],
  (machineState, { callId, name }) =>
    (callId &&
      getList(machineState, callId)?.groups?.find(
        (group) => group.name === name
      )) ||
    null
);

/**
 * Get the groups for a machine list request with a given callId.
 */
const listGroups = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => getList(machineState, callId)?.groups || []
);

/**
 * Get the loaded state for a machine list request with a given callId.
 */
const listLoaded = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => getList(machineState, callId)?.loaded ?? false
);

/**
 * Get the loading stateo for a machine list request with a given callId.
 */
const listLoading = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => getList(machineState, callId)?.loading ?? false
);

/**
 * Get machines in a list request.
 * @param state - The redux state.
 * @param callId - A list request id.
 * @param selected - Whether to filter for selected machines.
 * @returns A list of machines.
 */
const list = createCachedSelector(
  machineState,
  defaultSelectors.all,
  (_state: RootState, callId: string | null | undefined) => callId,
  (machineState, allMachines, callId) => {
    const machines: Machine[] = [];
    getList(machineState, callId)?.groups?.forEach((group) => {
      group.items.forEach((systemId) => {
        const machine = allMachines.find(
          ({ system_id }) => system_id === systemId
        );
        if (machine) {
          machines.push(machine);
        }
      });
    });
    return machines;
  }
)((_state, callId) => callId || "");

/**
 * Get machine system_ids in a list request.
 * @param state - The redux state.
 * @param callId - A list request id.
 * @param selected - Whether to filter for selected machines.
 * @returns A list of machines.
 */
const listIds = createCachedSelector(
  machineState,
  (_state: RootState, callId: string | null | undefined) => callId,
  (machineState, callId) => {
    const ids: Machine[MachineMeta.PK][] = [];
    // Get the ids for all machines in a list or count re
    const list = getList(machineState, callId);
    if (list) {
      // Get the ids for all machines in a list request matching the callId
      list.groups?.forEach((group) => {
        group.items.forEach((systemId) => {
          if (!ids.includes(systemId)) {
            ids.push(systemId);
          }
        });
      });
    }
    return ids;
  }
)((_state, callId) => callId || "");

/**
 * Get the ids of machines in a list or details call that are not being used
 * by other calls.
 * @param state - The redux state.
 * @param callId - A list request id.
 * @returns A list of unused machine ids.
 */
const unusedIdsInCall = createSelector(
  [
    machineState,
    (_state: RootState, callId: string | null | undefined) => callId,
  ],
  (machineState, callId) => {
    const usedIds: Machine[MachineMeta.PK][] = [];
    // Get the ids for all machines in list and details requests, ignoring the
    // current request.
    Object.entries(machineState.details).forEach(
      ([detailsCallId, { system_id }]) => {
        if (detailsCallId !== callId) {
          usedIds.push(system_id);
        }
      }
    );
    Object.entries(machineState.lists).forEach(
      ([detailsCallId, { groups }]) => {
        if (detailsCallId !== callId) {
          groups?.forEach((group) => {
            group.items.forEach((systemId) => {
              usedIds.push(systemId);
            });
          });
        }
      }
    );
    const unusedIds: Machine[MachineMeta.PK][] = [];
    const details = getDetails(machineState, callId);
    const list = getList(machineState, callId);
    if (details) {
      // Check if the machine in the details request is used by any other requests.
      if (!usedIds.includes(details.system_id)) {
        unusedIds.push(details.system_id);
      }
    } else if (list) {
      // Find any machines in the list request that are not used by any other requests.
      list.groups?.forEach((group) => {
        group.items.forEach((systemId) => {
          if (!usedIds.includes(systemId)) {
            unusedIds.push(systemId);
          }
        });
      });
    }
    return unusedIds;
  }
);

const selectors = {
  ...defaultSelectors,
  aborting: statusSelectors.aborting,
  acquiring: statusSelectors.acquiring,
  active,
  activeID,
  checkingPower: statusSelectors.checkingPower,
  cloning: statusSelectors.cloning,
  commissioning: statusSelectors.commissioning,
  creatingPhysical: statusSelectors.creatingPhysical,
  creatingVlan: statusSelectors.creatingVlan,
  deleting: statusSelectors.deleting,
  deletingInterface: statusSelectors.deletingInterface,
  deploying: statusSelectors.deploying,
  detailsLoaded,
  detailsLoading,
  enteringRescueMode: statusSelectors.enteringRescueMode,
  eventErrors,
  eventErrorsForIds,
  exitingRescueMode: statusSelectors.exitingRescueMode,
  filterOptions,
  filterOptionsLoaded,
  filterOptionsLoading,
  filters,
  filtersLoaded,
  filtersLoading,
  getByStatusCode,
  getActionState,
  listIds,
  count,
  countLoaded,
  countLoading,
  countStale,
  getInterfaceById,
  getStatuses,
  getStatusForMachine,
  linkingSubnet: statusSelectors.linkingSubnet,
  list,
  listCount,
  listTotalPages,
  listErrors,
  listGroup,
  listGroups,
  listLoaded,
  listLoading,
  listStale,
  locking: statusSelectors.locking,
  markingBroken: statusSelectors.markingBroken,
  markingFixed: statusSelectors.markingFixed,
  overridingFailedTesting: statusSelectors.overridingFailedTesting,
  processing,
  releasing: statusSelectors.releasing,
  selected,
  settingPool: statusSelectors.settingPool,
  settingZone: statusSelectors.settingZone,
  statuses,
  tagging: statusSelectors.tagging,
  testing: statusSelectors.testing,
  turningOff: statusSelectors.turningOff,
  turningOn: statusSelectors.turningOn,
  unlocking: statusSelectors.unlocking,
  unlinkingSubnet: statusSelectors.unlinkingSubnet,
  untagging: statusSelectors.untagging,
  unusedIdsInCall,
  updatingTags,
};

export default selectors;
