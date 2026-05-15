import { createSelector } from "reselect";

import type { RootState } from "../root/types";
import type { NetworkInterface } from "../types/node";

import { DeviceMeta } from "@/app/store/device/types";
import type {
  Device,
  DeviceState,
  DeviceStatus,
  DeviceNetworkInterface,
} from "@/app/store/device/types";
import { FilterDevices, isDeviceDetails } from "@/app/store/device/utils";
import tagSelectors from "@/app/store/tag/selectors";
import {
  generateBaseSelectors,
  getInterfaceById as getInterfaceByIdUtil,
} from "@/app/store/utils";

const defaultSelectors = generateBaseSelectors<
  DeviceState,
  Device,
  DeviceMeta.PK
>(DeviceMeta.MODEL, DeviceMeta.PK);

/**
 * Get the device state object.
 * @param state - The redux state.
 * @returns The device state.
 */
const deviceState = (state: RootState): DeviceState => state[DeviceMeta.MODEL];

/**
 * Get the devices statuses.
 * @param state - The redux state.
 * @returns The device statuses.
 */
const statuses = createSelector(
  [deviceState],
  (deviceState) => deviceState.statuses
);

/**
 * Get the statuses for a device.
 * @param state - The redux state.
 * @param id - A device's system id.
 * @returns The device's statuses
 */
const getStatusForDevice = createSelector(
  [
    statuses,
    (
      _state: RootState,
      id: Device[DeviceMeta.PK] | null,
      status: keyof DeviceStatus
    ) => ({
      id,
      status,
    }),
  ],
  (allStatuses, { id, status }) =>
    id && id in allStatuses ? allStatuses[id][status] : false
);

/**
 * Returns the devices which are being deleted.
 * @param state - The redux state.
 * @returns Devices being deleted.
 */
const deleting = createSelector(
  [defaultSelectors.all, statuses],
  (devices, statuses) =>
    devices.filter((device) => statuses[device.system_id]?.deleting || false)
);

/**
 * Returns the devices which are having their zone set.
 * @param state - The redux state.
 * @returns Devices having their zone set.
 */
const settingZone = createSelector(
  [defaultSelectors.all, statuses],
  (devices, statuses) =>
    devices.filter((device) => statuses[device.system_id]?.settingZone || false)
);

/**
 * Select the event errors for all devices.
 * @param state - The redux state.
 * @returns The event errors.
 */
const eventErrors = createSelector(
  [deviceState],
  (deviceState) => deviceState.eventErrors
);

/**
 * Select the event errors for a device or devices.
 * @param ids - A device's system ID.
 * @param event - A device action event.
 * @returns The event errors for the device(s).
 */
const eventErrorsForDevices = createSelector(
  [
    eventErrors,
    (
      _state: RootState,
      ids: Device[DeviceMeta.PK] | Device[DeviceMeta.PK][] | null,
      event?: string | null
    ) => ({
      ids,
      event,
    }),
  ],
  (errors: DeviceState["eventErrors"][0][], { ids, event }) => {
    if (!errors || !ids) {
      return [];
    }
    // If a single id has been provided then turn into an array to operate over.
    const idArray = Array.isArray(ids) ? ids : [ids];
    return errors.reduce<DeviceState["eventErrors"][0][]>((matches, error) => {
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

/**
 * Returns currently active device's system_id.
 * @param state - The redux state.
 * @returns Active device system_id.
 */
const activeID = createSelector(
  [deviceState],
  (deviceState) => deviceState.active
);

/**
 * Returns currently active device.
 * @param state - The redux state.
 * @returns Active device.
 */
const active = createSelector(
  [defaultSelectors.all, activeID],
  (devices: Device[], activeID: Device[DeviceMeta.PK] | null) =>
    devices.find((device) => activeID === device.system_id)
);

/**
 * Returns selected device system_ids.
 * @param state - The redux state.
 * @returns Selected device system_ids.
 */
const selectedIDs = createSelector(
  [deviceState],
  (deviceState) => deviceState.selected
);

/**
 * Returns selected devices.
 * @param state - The redux state.
 * @returns Selected devices.
 */
const selected = createSelector(
  [defaultSelectors.all, selectedIDs],
  (devices: Device[], selectedIDs: Device[DeviceMeta.PK][]) =>
    selectedIDs.reduce<Device[]>((selectedDevices, id) => {
      const selectedDevice = devices.find((device) => id === device.system_id);
      if (selectedDevice) {
        selectedDevices.push(selectedDevice);
      }
      return selectedDevices;
    }, [])
);

/**
 * Get devices that match search terms.
 * @param state - The redux state.
 * @param terms - The search terms to match against.
 * @returns A filtered list of devices.
 */
const search = createSelector(
  [
    defaultSelectors.all,
    tagSelectors.all,
    (
      _state: RootState,
      terms: string | null,
      selectedIDs: Device[DeviceMeta.PK][]
    ) => ({
      terms,
      selectedIDs,
    }),
  ],
  (items: Device[], tags, { selectedIDs, terms }) => {
    if (!terms) {
      return items;
    }
    return FilterDevices.filterItems(items, terms, selectedIDs, { tags });
  }
);

/**
 * Get an interface by id.
 * @param state - The redux state.
 * @param deviceId - The id of the device the interface belongs to.
 * @param interfaceId - The id the interface.
 * @returns A network interface.
 */
const getInterfaceById = createSelector(
  [
    defaultSelectors.all,
    (
      _state: RootState,
      deviceId: Device[DeviceMeta.PK],
      interfaceId?: DeviceNetworkInterface["id"] | null,
      linkId?: NetworkInterface["id"] | null
    ) => ({
      interfaceId,
      linkId,
      deviceId,
    }),
  ],
  (items: Device[], { linkId, interfaceId, deviceId }) => {
    const device = items.find(({ system_id }) => system_id === deviceId);
    if (!isDeviceDetails(device)) {
      return null;
    }
    return getInterfaceByIdUtil(device, interfaceId, linkId);
  }
);

const selectors = {
  ...defaultSelectors,
  active,
  activeID,
  deleting,
  eventErrorsForDevices,
  getInterfaceById,
  getStatusForDevice,
  search,
  selected,
  selectedIDs,
  settingZone,
};

export default selectors;
