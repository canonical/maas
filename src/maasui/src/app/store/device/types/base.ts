import type { DeviceIpAssignment, DeviceMeta } from "./enum";

import type { APIError } from "@/app/base/types";
import type { ModelRef, TimestampFields } from "@/app/store/types/model";
import type {
  NetworkInterface,
  NodeActions,
  NodeLinkType,
  NodeType,
  NodeTypeDisplay,
  SimpleNode,
} from "@/app/store/types/node";
import type { EventError, GenericState } from "@/app/store/types/state";

export type DeviceActions = NodeActions.DELETE | NodeActions.SET_ZONE;

export type DeviceNetworkInterface = NetworkInterface & {
  ip_address: string | null;
  ip_assignment: DeviceIpAssignment;
};

export type BaseDevice = SimpleNode & {
  actions: DeviceActions[];
  extra_macs: string[];
  fabrics: string[];
  ip_address: string | null;
  ip_assignment: DeviceIpAssignment | "";
  link_speeds: number[];
  link_type: NodeLinkType.DEVICE;
  node_type_display: NodeTypeDisplay.DEVICE;
  owner: string;
  parent: string | null; // `parent` is a `system_id`
  primary_mac: string;
  spaces: string[];
  subnets: string[];
  zone: ModelRef;
};

export type DeviceDetails = BaseDevice &
  TimestampFields & {
    description: string;
    interfaces: DeviceNetworkInterface[];
    locked: boolean;
    node_type: typeof NodeType.DEVICE;
    on_network: boolean;
    pool: ModelRef | null;
    swap_size: number | null;
  };

export type Device = BaseDevice | DeviceDetails;

export type DeviceStatus = {
  creatingInterface: boolean;
  creatingPhysical: boolean;
  deleting: boolean;
  deletingInterface: boolean;
  linkingSubnet: boolean;
  unlinkingSubnet: boolean;
  updatingInterface: boolean;
  settingZone: boolean;
};

export type DeviceStatuses = Record<Device[DeviceMeta.PK], DeviceStatus>;

export type DeviceState = GenericState<Device, APIError> & {
  active: Device[DeviceMeta.PK] | null;
  eventErrors: EventError<Device, APIError, DeviceMeta.PK>[];
  selected: Device[DeviceMeta.PK][];
  statuses: DeviceStatuses;
};
