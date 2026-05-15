import type { ValueOf } from "@canonical/react-components";

import { SortDirection } from "@/app/base/types";
import { PowerFieldScope } from "@/app/store/general/types";
import type {
  FetchFilters,
  Machine,
  MachineDetails,
  SelectedMachines,
  FilterGroupOptionType,
  MachineStateListGroup,
} from "@/app/store/machine/types";
import { FetchSortDirection, FilterGroupKey } from "@/app/store/machine/types";
import type { Tag, TagMeta } from "@/app/store/tag/types";
import { PowerState } from "@/app/store/types/enum";
import { NodeStatus, NodeStatusCode } from "@/app/store/types/node";

/**
 * Whether a machine has a Machine or MachineDetails type.
 * @param machine - The machine to check
 * @returns Whether the machine is MachineDetails.
 */
export const isMachineDetails = (
  machine?: Machine | null
  // Use "metadata" as the canary as it only exists for MachineDetails.
): machine is MachineDetails => !!machine && "metadata" in machine;

export type TagIdCountMap = Map<Tag[TagMeta.PK], number>;

/**
 * The tag ids for the given machines.
 * @param machines - The machines to get the tag ids from.
 * @returns A list of tag ids.
 */
export const getTagCountsForMachines = (machines: Machine[]): TagIdCountMap => {
  const ids = machines.reduce<Tag[TagMeta.PK][]>(
    (tagIds, machine) => tagIds.concat(machine.tags),
    []
  );
  const tagCounts = new Map();
  ids.forEach((id) => {
    if (!tagCounts.has(id)) {
      tagCounts.set(id, ids.filter((tagId) => tagId === id).length);
    }
  });
  return tagCounts;
};

/**
 * Get the power field scopes that are applicable to a machine.
 * @param machine - The machine to get the applicable field scopes.
 * @returns A list of applicable field scopes.
 */
export const getMachineFieldScopes = (machine: Machine): PowerFieldScope[] => {
  if (machine.pod) {
    return [PowerFieldScope.NODE];
  }
  return [PowerFieldScope.BMC, PowerFieldScope.NODE];
};

/**
 * @returns Whether this machine is deployed and has hardware sync enabled.
 */
export function isDeployedWithHardwareSync(
  machine?: Machine | null
): machine is MachineDetails & {
  enable_hw_sync: true;
  status: NodeStatus.DEPLOYED;
} {
  return (
    isMachineDetails(machine) &&
    machine.status === NodeStatus.DEPLOYED &&
    machine.enable_hw_sync === true
  );
}

/**
 * @returns Whether this machine failed to sync when it was scheduled.
 */
export const getHasSyncFailed = (machine?: Machine | null): boolean => {
  if (!isMachineDetails(machine) || !machine.enable_hw_sync) {
    return false;
  }
  return machine.is_sync_healthy === false;
};

/**
 * Map the table sort direction to the value to send to the fetch request.
 */
export const mapSortDirection = (
  sortDirection?: ValueOf<typeof SortDirection> | null
): FetchSortDirection | null => {
  switch (sortDirection) {
    case SortDirection.ASCENDING:
      return FetchSortDirection.Ascending;
    case SortDirection.DESCENDING:
      return FetchSortDirection.Descending;
    default:
      return null;
  }
};

/**
 * Convert selected machines state to filters that can be sent to the API.
 */
export const selectedToFilters = (
  selected: SelectedMachines | null
): FetchFilters | null => {
  if (!selected) {
    return null;
  }
  // If the selected state is a filter then there's not manipulation required.
  if ("filter" in selected) {
    return selected.filter;
  }
  const filter: Record<
    string,
    (FilterGroupOptionType | null)[] | FilterGroupOptionType | null
  > = {};
  // Map items to the id filter.
  if ("items" in selected && selected.items?.length) {
    filter[FilterGroupKey.Id] = selected.items;
  }
  // Map groups to their filter key.
  if (
    "groups" in selected &&
    selected.groups?.length &&
    "grouping" in selected &&
    selected.grouping
  ) {
    // The grouping value is the key of the filter.
    filter[selected.grouping] = selected.groups.map((group) => {
      if (typeof group === "string") {
        // String filters should be exact matches.
        return `=${group}`;
      }
      return group;
    });
  }
  return Object.values(filter).length > 0 ? filter : null;
};

/**
 * Convert selected machines state to separate filters to the API
 * which allows to get a match for items OR groups
 */
export const selectedToSeparateFilters = (
  selectedMachines: SelectedMachines | null
): { groupFilters: FetchFilters | null; itemFilters: FetchFilters | null } => {
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
  return {
    groupFilters,
    itemFilters,
  };
};

export const mergeGroupUpdates = ({
  initialGroups,
  updatedCollapsedGroups,
  updatedExpandedGroups,
}: Record<string, MachineStateListGroup[] | null>):
  | MachineStateListGroup[]
  | null => {
  let groups: MachineStateListGroup[] = [];
  if (
    initialGroups &&
    updatedCollapsedGroups &&
    updatedExpandedGroups &&
    updatedCollapsedGroups.length > 0 &&
    updatedExpandedGroups.length > 0
  ) {
    const initialCollapsedGroups = initialGroups.reduce<string[]>(
      (acc, curr) => {
        if (curr.collapsed && curr.name) {
          acc.push(curr.name);
        }
        return acc;
      },
      []
    );
    const filteredUpdatedCollapsedGroups = updatedCollapsedGroups?.filter(
      (group) =>
        !!group.collapsed &&
        initialCollapsedGroups.includes(group.name as string)
    );
    const filteredUpdatedExpandedGroups = updatedExpandedGroups?.filter(
      (group) => !group.collapsed
    );
    groups = [
      ...(filteredUpdatedCollapsedGroups ?? []),
      ...(filteredUpdatedExpandedGroups ?? []),
    ];
  } else {
    return initialGroups;
  }
  return groups;
};

export const isUnconfiguredPowerType = (machine: Machine): boolean => {
  return (
    machine.power_state === PowerState.UNKNOWN &&
    machine.status_code === NodeStatusCode.NEW
  );
};

export function getNodeStatusKey(
  value: string
): keyof typeof NodeStatus | undefined {
  for (const key in NodeStatus) {
    if (NodeStatus[key as keyof typeof NodeStatus] === value) {
      return key as keyof typeof NodeStatus;
    }
  }
  return undefined;
}
