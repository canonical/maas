import { FetchGroupKey } from "../types/actions";

import type { Machine, MachineStateListGroup } from "@/app/store/machine/types";
import { FetchNodeStatus, NodeStatus } from "@/app/store/types/node";
import { capitaliseFirst } from "@/app/utils";

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

/**
 * Machine properties are not a 1:1 mapping to grouping and require
 * additional logic to determine the correct grouping name and value
 * when creating a new group for a machine
 *
 * @param {FetchGroupKey} groupBy
 * @param {Machine} machine
 * @returns { name: string, value: string }
 */
export const createMachineListGroup = ({
  groupBy,
  machine,
}: {
  groupBy: FetchGroupKey;
  machine: Machine;
}): Pick<MachineStateListGroup, "name" | "value"> | null => {
  const groupKeyToMachineListGroupValue: Partial<
    Record<FetchGroupKey, string | null>
  > = {
    status: machine.status,
    owner: machine.owner,
    domain: machine.domain.name,
    pool: machine.pool.name,
    architecture: machine.architecture,
    parent: machine.parent,
    pod: machine.pod?.name || null, // KVM
    pod_type: machine.power_type, // KVM Type
    power_state: machine.power_state,
    zone: machine.zone.name,
  };

  const machineValue =
    groupBy && Object.values(FetchGroupKey).includes(groupBy)
      ? groupKeyToMachineListGroupValue[groupBy]
      : null;

  if (!machineValue) {
    return null;
  }

  switch (groupBy) {
    case FetchGroupKey.Status: {
      const nodeStatusKey = getNodeStatusKey(machineValue);
      return nodeStatusKey
        ? {
            name: machineValue,
            value: FetchNodeStatus[nodeStatusKey],
          }
        : null;
    }
    case FetchGroupKey.PowerState: {
      return {
        name: capitaliseFirst(machineValue),
        value: machineValue,
      };
    }
    default: {
      return {
        name: machineValue,
        value: machineValue,
      };
    }
  }
};
