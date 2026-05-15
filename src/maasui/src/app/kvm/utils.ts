import { formatBytes } from "@canonical/maas-react-components";

import type { KVMStoragePoolResource, KVMStoragePoolResources } from "./types";

import type { Pod } from "@/app/store/pod/types";

/**
 * Returns a string with the formatted byte value and unit, e.g 1024 => "1KiB"
 *
 * @param memory - the memory in bytes
 * @returns formatted memory string with value and unit
 */
export const memoryWithUnit = (memory: number): string => {
  const formatted = formatBytes({ value: memory, unit: "B" }, { binary: true });
  return `${formatted.value}${formatted.unit}`;
};

/**
 * Calculate the amount of free storage in a storage pool.
 * @param resource - The storage pool resource to calculate free storage.
 * @returns Free storage in pool.
 */
export const calcFreePoolStorage = (resource: KVMStoragePoolResource): number =>
  resource.total - resource.allocated_other - resource.allocated_tracked;

/**
 * Convert a pod or cluster's storage pool resources object into a sorted array.
 * @param pools - The pod or cluster's storage pool resources object.
 * @param defaultPoolId - the default pool id of the pod.
 * @returns a sorted list of storage pools in the pod or cluster.
 */
export const getSortedPoolsArray = (
  pools: KVMStoragePoolResources,
  defaultPoolId?: Pod["default_storage_pool"]
): [name: string, resource: KVMStoragePoolResource][] => {
  const poolsArray = Object.entries<KVMStoragePoolResource>(pools);

  return poolsArray.sort(([nameA, dataA], [nameB, dataB]) => {
    if (defaultPoolId && "id" in dataA && "id" in dataB) {
      // Pools in pods will have an id. For this case we sort by default first
      // (as defined in pod.default_storage_pool) then by id.
      if (
        dataA.id === defaultPoolId ||
        (dataB.id !== defaultPoolId && dataA.id < dataB.id)
      ) {
        return -1;
      } else if (dataB.id === defaultPoolId || dataA.id > dataB.id) {
        return 1;
      }
      return 0;
    }

    // Pools in clusters do not have a single id, as they can span multiple
    // pods. For this case we just sort by name;
    if (nameA < nameB) {
      return -1;
    } else if (nameA > nameB) {
      return 1;
    }
    return 0;
  });
};
