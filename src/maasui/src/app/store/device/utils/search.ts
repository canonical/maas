import { DeviceMeta } from "@/app/store/device/types";
import type { Device } from "@/app/store/device/types";
import { getIpAssignmentDisplay } from "@/app/store/device/utils";
import type { Tag } from "@/app/store/tag/types/base";
import { getTagNamesForIds } from "@/app/store/tag/utils";
import type { FilterValue } from "@/app/utils/search/filter-handlers";
import {
  isFilterValue,
  isFilterValueArray,
} from "@/app/utils/search/filter-handlers";
import FilterItems from "@/app/utils/search/filter-items";

type ExtraData = {
  tags: Tag[];
};

type SearchMappings = Record<
  string,
  (device: Device, extraData?: ExtraData) => FilterValue | FilterValue[] | null
>;

// Helpers that convert the pseudo field on the device to an actual value.
const searchMappings: SearchMappings = {
  domain: (device: Device) => device.domain.name,
  ip_assignment: (device: Device) =>
    getIpAssignmentDisplay(device.ip_assignment),
  tags: (device, extraData) =>
    extraData?.tags ? getTagNamesForIds(device.tags, extraData.tags) : [],
  zone: (device: Device) => device.zone.name,
};

export const getDeviceValue = (
  device: Device,
  filter: string,
  extraData?: ExtraData
): FilterValue | FilterValue[] | null => {
  const mapFunc = filter in searchMappings ? searchMappings[filter] : null;
  let value: FilterValue | FilterValue[] | null = null;
  if (mapFunc) {
    value = mapFunc(device, extraData);
  } else if (device.hasOwnProperty(filter)) {
    const deviceValue = device[filter as keyof Device];
    // Only return values that are valid for filters, all other values should
    // use the map function above.
    if (isFilterValue(deviceValue) || isFilterValueArray(deviceValue)) {
      value = deviceValue;
    }
  }
  return value;
};

export const FilterDevices = new FilterItems<Device, DeviceMeta.PK, ExtraData>(
  DeviceMeta.PK,
  getDeviceValue
);
