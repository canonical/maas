import type { Device, DeviceDetails } from "@/app/store/device/types";
import { DeviceIpAssignment } from "@/app/store/device/types";

/**
 * Returns whether a device is of type DeviceDetails.
 * @param device - The device to check
 * @returns Whether the device is of type DeviceDetails.
 */
export const isDeviceDetails = (
  device?: Device | null
  // Use "interfaces" as the canary as it only exists for DeviceDetails.
): device is DeviceDetails => !!device && "interfaces" in device;

/**
 * Returns the UI-friendly display for a device's IP assignment
 * @param ipAssignment - The device's IP assignment to check
 * @returns UI-friendly device IP assignment.
 */
export const getIpAssignmentDisplay = (
  ipAssignment?: Device["ip_assignment"] | null
): string => {
  switch (ipAssignment) {
    case DeviceIpAssignment.DYNAMIC:
      return "Dynamic";
    case DeviceIpAssignment.EXTERNAL:
      return "Static (Externally managed)";
    case DeviceIpAssignment.STATIC:
      return "Static (Client configured)";
    default:
      return "Unknown";
  }
};
