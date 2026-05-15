import { useCallback, useEffect, useMemo, useState } from "react";

import type { ValueOf } from "@canonical/react-components";
import { usePrevious } from "@canonical/react-components/dist/hooks";
import type { AnyAction } from "@reduxjs/toolkit";
import { nanoid } from "@reduxjs/toolkit";
import fastDeepEqual from "fast-deep-equal";
import { useDispatch, useSelector } from "react-redux";

import { FetchGroupKey } from "../types/actions";
import type { FetchParams } from "../types/actions";

import { selectedToFilters, selectedToSeparateFilters } from "./common";
import { generateCallId, transformToFetchParams } from "./query";
import { FilterMachines } from "./search";

import { ACTION_STATUS } from "@/app/base/constants";
import { useFetchActions, useCanEdit } from "@/app/base/hooks";
import type {
  ActionStatuses,
  ActionState,
  APIError,
  SortDirection,
} from "@/app/base/types";
import ErrorDetails from "@/app/machines/components/ErrorDetails";
import type { MachineActionFormProps } from "@/app/machines/types";
import { generalActions } from "@/app/store/general";
import {
  architectures as architecturesSelectors,
  osInfo as osInfoSelectors,
} from "@/app/store/general/selectors";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type {
  FetchFilters,
  Machine,
  MachineMeta,
  MachineStateListGroup,
  SelectedMachines,
} from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { Host } from "@/app/store/types/host";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";
import { FetchNodeStatus, NodeStatus } from "@/app/store/types/node";
import {
  getLinkInterface,
  hasInterfaceType,
  isNodeStorageConfigurable,
} from "@/app/store/utils";
import vlanSelectors from "@/app/store/vlan/selectors";
import { isId } from "@/app/utils";

export const useDispatchWithCallId = <A extends AnyAction>(): {
  callId: string | null;
  dispatch: (args: A) => A & { meta: { callId: string } };
} => {
  const [callId, setCallId] = useState<string | null>(nanoid());
  const dispatch = useDispatch();

  const handleDispatch = useCallback(
    (args: A) => {
      const callId = nanoid();
      setCallId(callId);
      return dispatch({ ...args, meta: { ...args.meta, callId } });
    },
    [dispatch, setCallId]
  );

  useEffect(() => {
    return () => {
      if (callId) {
        dispatch(machineActions.removeRequest(callId));
      }
    };
  }, [callId, dispatch]);

  return {
    callId,
    dispatch: (args: A) =>
      handleDispatch({ ...args, meta: { ...args.meta, callId } }),
  };
};

type MachineActionData = {
  actionStatus: ActionState["status"];
  actionErrors: ActionState["errors"];
  successCount: ActionState["successCount"];
  failedSystemIds: ActionState["failedSystemIds"];
};

export const useMachineActionDispatch = <
  A extends AnyAction,
>(): MachineActionData & {
  dispatch: (args: A) => void;
} => {
  const { callId: dispatchCallId, dispatch: dispatchWithCallId } =
    useDispatchWithCallId();
  const actionState = useSelector((state: RootState) =>
    machineSelectors.getActionState(state, dispatchCallId)
  );
  const actionStatus = actionState?.status || ACTION_STATUS.idle;
  const failedSystemIds = actionState?.failedSystemIds || [];
  const failedSystemIdsCount = failedSystemIds.length ?? 0;

  const actionErrors =
    actionState && failedSystemIdsCount > 0 ? (
      <ErrorDetails {...actionState} />
    ) : null;

  return {
    dispatch: dispatchWithCallId,
    actionStatus: actionStatus,
    actionErrors: actionState?.errors || actionErrors || null,
    successCount: actionState?.successCount || 0,
    failedSystemIds,
  };
};

export const getCombinedActionStatus = (
  ...statuses: ActionStatuses[]
): ActionStatuses => {
  // if either is loading, return loading
  if (statuses.some((status) => status === ACTION_STATUS.loading)) {
    return ACTION_STATUS.loading;
  }

  // if either has failed and the other is not loading, return failed
  if (
    statuses.some((status) => status === ACTION_STATUS.error) &&
    statuses.every((status) => status !== ACTION_STATUS.loading)
  ) {
    return ACTION_STATUS.error;
  }

  // if either has succeeded and the other is not loading, return succeeded
  if (
    statuses.some((status) => status === ACTION_STATUS.success) &&
    statuses.every((status) => status !== ACTION_STATUS.loading)
  ) {
    return ACTION_STATUS.success;
  }

  return ACTION_STATUS.idle;
};

/**
 * Dispatch machine action(s) for selected machines
 * Will dispatch multiple  actions when there are selected both groups and items
 */
export const useSelectedMachinesActionsDispatch = ({
  selectedMachines,
  searchFilter,
}: {
  selectedMachines?: SelectedMachines | null;
  searchFilter?: string;
}): MachineActionData & {
  dispatch: (
    a: ValueOf<typeof machineActions>,
    args?: Record<string, unknown> & { filter?: never }
  ) => void;
} => {
  const {
    dispatch: groupsDispatch,
    actionStatus: groupsActionStatus,
    successCount: groupsSuccessCount,
    actionErrors: groupsActionErrors,
    failedSystemIds: groupsFailedSystemIds,
  } = useMachineActionDispatch();
  const {
    dispatch: itemsDispatch,
    actionStatus: itemsActionStatus,
    successCount: itemsSuccessCount,
    actionErrors: itemsActionErrors,
    failedSystemIds: itemsFailedSystemIds,
  } = useMachineActionDispatch();
  const searchFilters: FetchFilters = useMemo(
    () => (searchFilter ? FilterMachines.parseFetchFilters(searchFilter) : {}),
    [searchFilter]
  );
  const getIsSingleFilter = (
    selectedMachines?: SelectedMachines | null
  ): selectedMachines is { filter: FetchFilters } => {
    if (selectedMachines && "filter" in selectedMachines) {
      return true;
    }
    return false;
  };
  const isSingleFilter = getIsSingleFilter(selectedMachines);

  // Dispatch items and groups actions separately
  // - otherwise the action would only be run on machines
  // matching both groups and items selected
  const groupFilters = selectedToFilters(
    isSingleFilter
      ? { filter: selectedMachines?.filter }
      : {
          groups: selectedMachines?.groups,
          grouping: selectedMachines?.grouping,
        }
  );
  const itemFilters = selectedToFilters(
    !isSingleFilter ? { items: selectedMachines?.items } : null
  );

  const dispatch = useCallback(
    // TODO: add strict action type for useSelectedMachinesActionsDispatch https://warthogs.atlassian.net/browse/MAASENG-2121
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (action: (...args: any[]) => AnyAction, args?: Record<string, unknown>) => {
      if (groupFilters) {
        groupsDispatch(
          action({
            ...args,
            filter: { ...groupFilters, ...searchFilters },
          })
        );
      }
      if (itemFilters) {
        itemsDispatch(
          action({
            ...args,
            filter: { ...itemFilters, ...searchFilters },
          })
        );
      }
    },
    [groupsDispatch, itemsDispatch, groupFilters, itemFilters, searchFilters]
  );

  let actionStatus: ActionStatuses = ACTION_STATUS.idle;

  if (groupFilters && itemFilters) {
    actionStatus = getCombinedActionStatus(
      groupsActionStatus,
      itemsActionStatus
    );
  } else {
    actionStatus = groupFilters ? groupsActionStatus : itemsActionStatus;
  }

  return {
    dispatch,
    actionStatus,
    actionErrors: groupsActionErrors || itemsActionErrors,
    successCount: groupsSuccessCount + itemsSuccessCount,
    failedSystemIds: [
      ...(groupsFailedSystemIds || []),
      ...(itemsFailedSystemIds || []),
    ],
  };
};

export const useMachineSelectedCount = (
  filters: FetchFilters | null,
  queryOptions?: UseFetchQueryOptions
): {
  selectedCount: number;
  selectedCountLoading: boolean;
} => {
  const { isEnabled } = queryOptions || { isEnabled: true };
  const selectedState = useSelector(machineSelectors.selected);
  let selectedCount = 0;
  // Shallow clone the selected state so that object can be modified.
  const selectedMachines = selectedState ? { ...selectedState } : null;
  // Remove selected items from the filters to send to the API. We can count
  // them client side and filters are combined with AND which we don't want to do when
  // there are selected groups and items (otherwise it will be counting the
  // machines that match both the groups and the items).
  if (selectedMachines && "items" in selectedMachines) {
    selectedCount += selectedMachines.items?.length ?? 0;
    delete selectedMachines.items;
  }
  // Get the count of machines in selected groups or filters.
  const filtersFromSelected = selectedToFilters(selectedMachines);
  const {
    machineCount: fetchedSelectedCount,
    machineCountLoading: selectedLoading,
  } = useFetchMachineCount(
    { ...filters, ...filtersFromSelected },
    { isEnabled: isEnabled && filtersFromSelected !== null }
  );
  // Only add the count if there are filters as sending `null` filters
  // to the count API will return a count of all machines.
  if (filtersFromSelected) {
    selectedCount += fetchedSelectedCount;
  }
  const onlyHasItems =
    !!selectedMachines &&
    selectedCount > 0 &&
    (!("groups" in selectedMachines) || !selectedMachines?.groups?.length);

  return {
    selectedCount,
    selectedCountLoading:
      // There's no need to wait for the selected count to respond if there
      // are only items as we can count them client side.
      onlyHasItems ? false : selectedLoading,
  };
};

/**
 * Fetch selected machines machines via the API
 * This will ensure we have all data needed for selected machines
 * (including those in collapsed groups or out of bounds of the currently visible page)
 */
export const useFetchSelectedMachines = (
  queryOptions: UseFetchQueryOptions
): Omit<UseFetchMachinesData, "totalPages"> => {
  const { isEnabled } = queryOptions || { isEnabled: true };
  const selectedMachines = useSelector(machineSelectors.selected);
  const getIsSingleFilter = (
    selectedMachines: SelectedMachines | null
  ): selectedMachines is { filter: FetchFilters } => {
    if (selectedMachines && "filter" in selectedMachines) {
      return true;
    }
    return false;
  };
  const isSingleFilter = getIsSingleFilter(selectedMachines);
  // Fetch items and groups separately
  // - otherwise the back-end will return machines
  // matching both groups and items
  const groupFilters = selectedToFilters(
    isSingleFilter
      ? { filter: selectedMachines?.filter }
      : {
          groups: selectedMachines?.groups,
          grouping: selectedMachines?.grouping,
        }
  );
  const itemFilters = selectedToFilters(
    !isSingleFilter ? { items: selectedMachines?.items } : null
  );
  const groupData = useFetchMachines(
    {
      filters: groupFilters,
    },
    { isEnabled: isEnabled && groupFilters !== null }
  );
  const itemsData = useFetchMachines(
    {
      filters: itemFilters,
    },
    {
      // skip separate items call if there is a single filter
      isEnabled: isEnabled && !isSingleFilter,
    }
  );

  return {
    callId: null,
    machines: [...groupData.machines, ...itemsData.machines],
    loading: groupData.loading || itemsData.loading,
    loaded: groupFilters
      ? groupData.loaded
      : true && itemFilters
        ? itemsData.loaded
        : true,
    machineCount: groupData.machineCount || 0 + (itemsData?.machineCount || 0),
    machinesErrors: groupData.machinesErrors || itemsData.machinesErrors,
  };
};

export const useFetchMachineCount = (
  filters?: FetchFilters | null,
  queryOptions?: UseFetchQueryOptions
): {
  machineCount: number;
  machineCountLoading: boolean;
  machineCountLoaded: boolean;
} => {
  const { isEnabled } = queryOptions || { isEnabled: true };
  const previousIsEnabled = usePrevious(isEnabled);
  const [callId, setCallId] = useState<string | null>(null);
  const [staleCount, setStaleCount] = useState<number>(0);
  const previousStaleCount = usePrevious(staleCount);
  const previousCallId = usePrevious(callId);
  const previousFilters = usePrevious(filters);
  const isStale = useSelector((state: RootState) =>
    machineSelectors.countStale(state, callId)
  );
  useEffect(() => {
    if (isStale) {
      setStaleCount((count) => count + 1);
    }
  }, [isStale]);
  const dispatch = useDispatch();
  const machineCount = useSelector((state: RootState) =>
    machineSelectors.count(state, callId)
  );
  const machineCountLoading = useSelector((state: RootState) =>
    machineSelectors.countLoading(state, callId)
  );
  const machineCountLoaded = useSelector((state: RootState) =>
    machineSelectors.countLoaded(state, callId)
  );

  useEffect(() => {
    // undefined, null and {} are all equivalent i.e. no filters so compare the
    // current and previous filters using an empty object if the filters are falsy.
    if (isEnabled) {
      if (
        !fastDeepEqual(filters || {}, previousFilters || {}) ||
        !callId ||
        isEnabled !== previousIsEnabled
      ) {
        setCallId(generateCallId(filters));
      }
    }
  }, [
    callId,
    dispatch,
    filters,
    previousFilters,
    isEnabled,
    previousIsEnabled,
  ]);

  useEffect(() => {
    if (
      (isEnabled && callId && isEnabled !== previousIsEnabled) ||
      (isEnabled && callId && callId !== previousCallId) ||
      (isEnabled && callId && staleCount !== previousStaleCount)
    ) {
      dispatch(machineActions.count(callId, filters));
    }
  }, [
    dispatch,
    filters,
    callId,
    previousCallId,
    isEnabled,
    previousIsEnabled,
    staleCount,
    previousStaleCount,
  ]);

  return {
    machineCount: machineCount || 0,
    machineCountLoading,
    machineCountLoaded,
  };
};

/**
 * Fetch a count of deployed machines for a given filter and selected machines via the API
 */
export const useFetchDeployedMachineCount = ({
  selectedMachines,
  searchFilter,
}: Pick<MachineActionFormProps, "searchFilter" | "selectedMachines">): {
  machineCount: number;
} => {
  const searchFilters = searchFilter
    ? FilterMachines.parseFetchFilters(searchFilter)
    : {};
  const { groupFilters, itemFilters } = selectedMachines
    ? selectedToSeparateFilters(selectedMachines)
    : { groupFilters: null, itemFilters: null };
  const { machineCount: itemsMachineCount } = useFetchMachineCount(
    {
      ...itemFilters,
      ...searchFilters,
      status: FetchNodeStatus.DEPLOYED,
    },
    { isEnabled: !!itemFilters }
  );

  // Assume count as 0 if grouping by status and group other than deployed is selected
  let isGroupCountEnabled = false;
  if (
    selectedMachines &&
    "groups" in selectedMachines &&
    selectedMachines?.groups?.includes(FetchNodeStatus.DEPLOYED)
  ) {
    isGroupCountEnabled = true;
  } else if (
    selectedMachines &&
    "grouping" in selectedMachines &&
    selectedMachines?.grouping !== FetchGroupKey.Status
  ) {
    isGroupCountEnabled = true;
    // if all machines are selected, fetch deployed machine count for all machines
  } else if (selectedMachines && "filter" in selectedMachines) {
    isGroupCountEnabled = true;
  }
  const { machineCount: groupsMachineCount } = useFetchMachineCount(
    {
      ...groupFilters,
      ...searchFilters,
      status: FetchNodeStatus.DEPLOYED,
    },
    {
      isEnabled: isGroupCountEnabled,
    }
  );

  return {
    machineCount: groupsMachineCount + itemsMachineCount,
  };
};

export type UseFetchMachinesOptions = {
  filters?: FetchFilters | null;
  grouping?: FetchGroupKey | null;
  sortKey?: FetchGroupKey | string | null;
  sortDirection?: ValueOf<typeof SortDirection> | null;
  collapsedGroups?: FetchParams["group_collapsed"];
  pagination?: {
    pageSize: number;
    currentPage: number;
    setCurrentPage: React.Dispatch<React.SetStateAction<number>>;
  };
};

export type UseFetchQueryOptions = {
  isEnabled?: boolean;
};

type UseFetchMachinesData = {
  callId: string | null;
  loaded: boolean;
  loading: boolean;
  machineCount: number | null;
  machines: Machine[];
  machinesErrors: APIError;
  totalPages: number | null;
};

/**
 * Fetch machines via the API.
 */
export const useFetchMachines = (
  options?: UseFetchMachinesOptions | null,
  queryOptions?: UseFetchQueryOptions
): UseFetchMachinesData & {
  groups: MachineStateListGroup[] | null;
  cleanup: () => void;
} => {
  const { isEnabled } = queryOptions || { isEnabled: true };
  const previousIsEnabled = usePrevious(isEnabled);
  const [callId, setCallId] = useState<string | null>(null);
  const previousCallId = usePrevious(callId);
  const previousOptions = usePrevious(options, false);
  const [staleCount, setStaleCount] = useState<number>(0);
  const previousStaleCount = usePrevious(staleCount);
  const isStale = useSelector((state: RootState) =>
    machineSelectors.listStale(state, callId)
  );

  useEffect(() => {
    if (isStale) {
      setStaleCount((count) => count + 1);
    }
  }, [isStale]);

  const dispatch = useDispatch();
  const machines = useSelector((state: RootState) =>
    machineSelectors.list(state, callId)
  );
  const groups = useSelector((state: RootState) =>
    machineSelectors.listGroups(state, callId)
  );
  const machineCount = useSelector((state: RootState) =>
    machineSelectors.listCount(state, callId)
  );
  const totalPages = useSelector((state: RootState) =>
    machineSelectors.listTotalPages(state, callId)
  );
  const machinesErrors = useSelector((state: RootState) =>
    machineSelectors.listErrors(state, callId)
  );
  const loaded = useSelector((state: RootState) =>
    machineSelectors.listLoaded(state, callId)
  );
  const loading = useSelector((state: RootState) =>
    machineSelectors.listLoading(state, callId)
  );
  const cleanup = () => {
    if (callId) {
      dispatch(machineActions.cleanupRequest(callId));
    }
  };
  useCleanup(callId);

  // reset pagination when filters change
  const { filters, grouping, collapsedGroups, sortDirection, sortKey } =
    options || {};
  const filterOptions = useMemo(
    () => ({
      filters,
      grouping,
      collapsedGroups,
      sortDirection,
      sortKey,
    }),
    [filters, grouping, collapsedGroups, sortDirection, sortKey]
  );
  const previousFilterOptions = usePrevious(filterOptions);
  useEffect(() => {
    if (!fastDeepEqual(filterOptions, previousFilterOptions)) {
      options?.pagination?.setCurrentPage?.(1);
    }
  }, [options, filterOptions, previousFilterOptions]);

  useEffect(() => {
    // undefined, null and {} are all equivalent i.e. no filters so compare the
    // current and previous filters using an empty object if the filters are falsy.
    if (isEnabled) {
      if (
        !fastDeepEqual(options || {}, previousOptions || {}) ||
        !callId ||
        isEnabled !== previousIsEnabled
      ) {
        setCallId(generateCallId(transformToFetchParams(options)));
      }
    }
  }, [
    callId,
    dispatch,
    options,
    previousOptions,
    isEnabled,
    previousIsEnabled,
  ]);

  useEffect(() => {
    if (
      (isEnabled && callId && isEnabled !== previousIsEnabled) ||
      (isEnabled && callId && callId !== previousCallId) ||
      (isEnabled && callId && staleCount !== previousStaleCount)
    ) {
      dispatch(machineActions.fetch(callId, transformToFetchParams(options)));
    }
  }, [
    callId,
    dispatch,
    options,
    previousCallId,
    isEnabled,
    previousIsEnabled,
    staleCount,
    previousStaleCount,
  ]);

  return {
    callId,
    cleanup,
    loaded,
    loading,
    groups,
    machineCount,
    totalPages,
    machines,
    machinesErrors,
  };
};

/**
 * Fetch a machine via the API.
 * @param id - A machine's system id.
 */
export const useFetchMachine = (
  id?: Machine[MachineMeta.PK] | null
): {
  machine: Machine | null;
  loading?: boolean;
  loaded?: boolean;
  error: APIError;
} => {
  const [callId, setCallId] = useState<string | null>(null);
  const previousId = usePrevious(id, false);
  const previousCallId = usePrevious(callId);
  const dispatch = useDispatch();
  const loaded = useSelector((state: RootState) =>
    machineSelectors.detailsLoaded(state, callId)
  );
  const loading = useSelector((state: RootState) =>
    machineSelectors.detailsLoading(state, callId)
  );
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  const error = useSelector((state: RootState) =>
    machineSelectors.errors(state)
  );
  useCleanup(callId);

  useEffect(() => {
    if (isId(id) && id !== previousId) {
      const newId = nanoid();
      setCallId(newId);
    }
  }, [dispatch, id, previousId]);

  useEffect(() => {
    if (isId(id) && callId && callId !== previousCallId) {
      dispatch(machineActions.get(id, callId));
    }
  }, [dispatch, id, callId, previousCallId]);

  return {
    machine,
    loading,
    loaded,
    error,
  };
};

/**
 * Unsubscribe from machines if they're no longer being used.
 */
const useCleanup = (callId: string | null): void => {
  const dispatch = useDispatch();

  useEffect(() => {
    return () => {
      if (callId) {
        dispatch(machineActions.cleanupRequest(callId));
      }
    };
  }, [callId, dispatch]);
};

/**
 * Check whether a machine's storage can be edited based on permissions and the
 * machine's status.
 * @param machine - A machine object.
 * @returns Whether the machine's storage can be edited.
 */
export const useCanEditStorage = (machine: Machine | null): boolean => {
  const canEdit = useCanEdit(machine);
  const machineStorageConfigurable = isNodeStorageConfigurable(machine);
  return canEdit && machineStorageConfigurable;
};

/**
 * Format a node's OS and release into human-readable text.
 * @param node - A node object.
 * @param hideUbuntuTitle - Whether to hide the title of the Ubuntu release
 * @returns Formatted OS string.
 */
export const useFormattedOS = (
  node?: Host | null,
  hideUbuntuTitle?: boolean
): string => {
  const loading = useSelector(osInfoSelectors.loading);
  const osReleases = useSelector((state: RootState) =>
    osInfoSelectors.getOsReleases(state, node?.osystem)
  );

  useFetchActions([generalActions.fetchOsInfo]);

  if (!node || !node.osystem || !node.distro_series || loading) {
    return "";
  }

  const machineRelease = osReleases.find(
    (release) => release.value === node.distro_series
  );
  if (machineRelease) {
    return node.osystem === "ubuntu" && hideUbuntuTitle
      ? machineRelease.label.split('"')[0].trim()
      : machineRelease.label;
  }
  return `${node.osystem}/${node.distro_series}`;
};

/**
 * Check if a machine has an invalid architecture.
 * @param machine - A machine object.
 * @returns Whether the machine has an invalid architecture.
 */
export const useHasInvalidArchitecture = (
  machine?: Machine | null
): boolean => {
  const architectures = useSelector(architecturesSelectors.get);

  useFetchActions([generalActions.fetchArchitectures]);

  if (!machine) {
    return false;
  }

  return (
    machine.architecture === "" || !architectures.includes(machine.architecture)
  );
};

/**
 * Check if only the name or mac address of an interface can
 * be edited.
 * @param nic - A network interface.
 * @param machine - A machine.
 * @return Whether limited editing is allowed.
 */
export const useIsLimitedEditingAllowed = (
  nic: NetworkInterface | null | undefined,
  machine: Machine | null | undefined,
  link?: NetworkLink | null
): boolean => {
  const canEdit = useCanEdit(machine);
  if (!canEdit || !machine) {
    return false;
  }
  if (link && !nic) {
    [nic] = getLinkInterface(machine, link);
  }
  return (
    !!nic &&
    machine?.status === NodeStatus.DEPLOYED &&
    !hasInterfaceType(NetworkInterfaceTypes.VLAN, machine, nic, link)
  );
};

/**
 * Check if a VLAN can be added to the interface.
 * @param machine - A machine.
 * @param nic - A network interface.
 * @return Whether limited editing is allowed.
 */
export const useCanAddVLAN = (
  machine?: Machine | null,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): boolean => {
  const unusedVLANs = useSelector((state: RootState) =>
    vlanSelectors.getUnusedForInterface(state, machine, nic)
  );
  if (
    !machine ||
    !nic ||
    hasInterfaceType(
      [NetworkInterfaceTypes.ALIAS, NetworkInterfaceTypes.VLAN],
      machine,
      nic,
      link
    )
  ) {
    return false;
  }
  // Check that there are unused VLANS available.
  return unusedVLANs.length > 0;
};

/**
 * Whether any machines are selected.
 */
export const useHasSelection = (): boolean => {
  const selectedMachines = useSelector(machineSelectors.selected);
  if (!selectedMachines) {
    return false;
  }
  // Check if the filter param is set. The just checks for a truthy value (instead
  // of checking if there are any keys) as an empty object is equivalent to
  // "select all".
  const hasFilters = "filter" in selectedMachines && !!selectedMachines.filter;
  const hasGroups =
    "groups" in selectedMachines && (selectedMachines.groups ?? [])?.length > 0;
  const hasItems =
    "items" in selectedMachines && (selectedMachines.items ?? [])?.length > 0;
  return hasFilters || hasGroups || hasItems;
};

/**
 * Return the previous count while a new fetch is in progress.
 */
export const useFetchedCount = (
  newCount: number | null,
  loading?: boolean | null
): number => {
  const [previousCount, setPreviousCount] = useState(newCount);
  const count = (loading ? previousCount : newCount) ?? 0;

  useEffect(() => {
    // The pagination needs to be displayed while the new list is being fetched
    // so this stores the previous machine count while the request is in progress.
    if ((newCount || newCount === 0) && previousCount !== newCount) {
      setPreviousCount(newCount);
    }
  }, [newCount, previousCount]);

  return count;
};
