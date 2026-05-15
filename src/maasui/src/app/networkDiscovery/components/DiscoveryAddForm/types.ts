import type {
  Device,
  DeviceIpAssignment,
  DeviceMeta,
} from "@/app/store/device/types";
import type { Domain } from "@/app/store/domain/types";

export enum DeviceType {
  DEVICE = "device",
  INTERFACE = "interface",
}

export type DiscoveryAddValues = {
  [DeviceMeta.PK]: Device[DeviceMeta.PK];
  domain: Domain["name"];
  hostname: Device["hostname"];
  ip_assignment: DeviceIpAssignment;
  parent: Device["parent"];
  type: DeviceType | "";
};
