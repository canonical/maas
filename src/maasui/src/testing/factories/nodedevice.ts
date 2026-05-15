import { extend } from "cooky-cutter";

import { timestampedModel } from "./model";

import { HardwareType } from "@/app/base/enum";
import type { NodeDevice } from "@/app/store/nodedevice/types";
import { NodeDeviceBus } from "@/app/store/nodedevice/types";
import type { TimestampedModel } from "@/app/store/types/model";

export const nodeDevice = extend<TimestampedModel, NodeDevice>(
  timestampedModel,
  {
    bus_number: 0,
    bus: NodeDeviceBus.PCIE,
    commissioning_driver: "pcieport",
    device_number: 1,
    hardware_type: HardwareType.Node,
    node_id: 0,
    numa_node_id: 0,
    pci_address: "0000:00:00.0",
    physical_blockdevice_id: null,
    physical_interface_id: null,
    product_id: "def456",
    product_name: "Product name",
    vendor_id: "abc123",
    vendor_name: "Vendor name",
  }
);
