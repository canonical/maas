import type { DiscoveryResponse } from "@/app/apiclient";
import type { FilterValue } from "@/app/utils/search/filter-handlers";
import {
  isFilterValue,
  isFilterValueArray,
} from "@/app/utils/search/filter-handlers";
import FilterItems from "@/app/utils/search/filter-items";

export const getDiscoveryValue = (
  discovery: DiscoveryResponse,
  filter: string
): FilterValue | FilterValue[] | null => {
  let value: FilterValue | FilterValue[] | null = null;
  if (discovery.hasOwnProperty(filter)) {
    const discoveryValue = discovery[filter as keyof DiscoveryResponse];
    // Only return values that are valid for filters.
    if (isFilterValue(discoveryValue) || isFilterValueArray(discoveryValue)) {
      value = discoveryValue;
    }
  }
  return value;
};

export const FilterDiscoveries = new FilterItems<DiscoveryResponse, "id">(
  "id",
  getDiscoveryValue
);
