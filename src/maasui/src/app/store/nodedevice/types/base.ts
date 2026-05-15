import type { NodeDeviceBus } from "./enum";

import type { HardwareType } from "@/app/base/enum";
import type { APIError } from "@/app/base/types";
import type { Machine } from "@/app/store/machine/types";
import type { TimestampedModel } from "@/app/store/types/model";
import type {
  Disk,
  NetworkInterface,
  NodeNumaNode,
} from "@/app/store/types/node";
import type { GenericState } from "@/app/store/types/state";

export type NodeDevice = TimestampedModel & {
  bus_number: number;
  bus: NodeDeviceBus;
  commissioning_driver: string;
  device_number: number;
  hardware_type: HardwareType;
  node_id: Machine["id"];
  numa_node_id: NodeNumaNode["index"];
  pci_address?: string;
  physical_blockdevice_id: Disk["id"] | null;
  physical_interface_id: NetworkInterface["id"] | null;
  product_id: string;
  product_name: string;
  vendor_id: string;
  vendor_name: string;
};

export type NodeDeviceState = GenericState<NodeDevice, APIError>;
