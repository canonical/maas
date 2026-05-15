import type {
  BridgeType,
  DiskTypes,
  NetworkInterfaceTypes,
  NetworkLinkMode,
} from "./enum";

import type { ZoneResponse } from "@/app/apiclient";
import type {
  Controller,
  ControllerDetails,
  ControllerMeta,
} from "@/app/store/controller/types";
import type {
  Device,
  DeviceDetails,
  DeviceMeta,
} from "@/app/store/device/types";
import type {
  BondLacpRate,
  BondMode,
  BondXmitHashPolicy,
} from "@/app/store/general/types";
import type {
  Machine,
  MachineDetails,
  MachineMeta,
} from "@/app/store/machine/types";
import type { Script } from "@/app/store/script/types";
import type { Subnet } from "@/app/store/subnet/types";
import type { Tag, TagMeta } from "@/app/store/tag/types";
import type {
  Model,
  ModelRef,
  TimestampedModel,
} from "@/app/store/types/model";
import type { VLAN, VLANMeta } from "@/app/store/vlan/types";

export const NodeType = {
  DEFAULT: 0,
  MACHINE: 0,
  DEVICE: 1,
  RACK_CONTROLLER: 2,
  REGION_CONTROLLER: 3,
  REGION_AND_RACK_CONTROLLER: 4,
} as const;

export type NodeType = (typeof NodeType)[keyof typeof NodeType];

export enum NodeTypeDisplay {
  DEVICE = "Device",
  MACHINE = "Machine",
  RACK_CONTROLLER = "Rack controller",
  REGION_AND_RACK_CONTROLLER = "Region and rack controller",
  REGION_CONTROLLER = "Region controller",
}

export enum NodeLinkType {
  CONTROLLER = "controller",
  DEVICE = "device",
  MACHINE = "machine",
}

export enum NodeStatusCode {
  // The node has been created and has a system ID assigned to it.
  NEW = 0,
  // Testing and other commissioning steps are taking place.
  COMMISSIONING = 1,
  // The commissioning step failed.
  FAILED_COMMISSIONING = 2,
  // The node can't be contacted.
  MISSING = 3,
  // The node is in the general pool ready to be deployed.
  READY = 4,
  // The node is ready for named deployment.
  RESERVED = 5,
  // The node has booted into the operating system of its owner's choice
  // and is ready for use.
  DEPLOYED = 6,
  // The node has been removed from service manually until an admin
  // overrides the retirement.
  RETIRED = 7,
  // The node is broken: a step in the node lifecycle failed.
  // More details can be found in the node's event log.
  BROKEN = 8,
  // The node is being installed.
  DEPLOYING = 9,
  // The node has been allocated to a user and is ready for deployment.
  ALLOCATED = 10,
  // The deployment of the node failed.
  FAILED_DEPLOYMENT = 11,
  // The node is powering down after a release request.
  RELEASING = 12,
  // The releasing of the node failed.
  FAILED_RELEASING = 13,
  // The node is erasing its disks.
  DISK_ERASING = 14,
  // The node failed to erase its disks.
  FAILED_DISK_ERASING = 15,
  // The node is in rescue mode.
  RESCUE_MODE = 16,
  // The node is entering rescue mode.
  ENTERING_RESCUE_MODE = 17,
  // The node failed to enter rescue mode.
  FAILED_ENTERING_RESCUE_MODE = 18,
  // The node is exiting rescue mode.
  EXITING_RESCUE_MODE = 19,
  // The node failed to exit rescue mode.
  FAILED_EXITING_RESCUE_MODE = 20,
  // Running tests on Node
  TESTING = 21,
  // Testing has failed
  FAILED_TESTING = 22,
}

export enum NodeStatus {
  ALLOCATED = "Allocated",
  BROKEN = "Broken",
  COMMISSIONING = "Commissioning",
  DEPLOYED = "Deployed",
  DEPLOYING = "Deploying",
  DISK_ERASING = "Disk erasing",
  ENTERING_RESCUE_MODE = "Entering rescue mode",
  EXITING_RESCUE_MODE = "Exiting rescue mode",
  FAILED_COMMISSIONING = "Failed commissioning",
  FAILED_DEPLOYMENT = "Failed deployment",
  FAILED_DISK_ERASING = "Failed disk erasing",
  FAILED_ENTERING_RESCUE_MODE = "Failed to enter rescue mode",
  FAILED_EXITING_RESCUE_MODE = "Failed to exit rescue mode",
  FAILED_RELEASING = "Releasing failed",
  FAILED_TESTING = "Failed testing",
  MISSING = "Missing",
  NEW = "New",
  READY = "Ready",
  RELEASING = "Releasing",
  RESCUE_MODE = "Rescue mode",
  RESERVED = "Reserved",
  RETIRED = "Retired",
  TESTING = "Testing",
}

export enum FetchNodeStatus {
  ALLOCATED = "allocated",
  BROKEN = "broken",
  COMMISSIONING = "commissioning",
  DEPLOYED = "deployed",
  DEPLOYING = "deploying",
  DISK_ERASING = "disk_erasing",
  ENTERING_RESCUE_MODE = "entering_rescue_mode",
  EXITING_RESCUE_MODE = "exiting_rescue_mode",
  FAILED_COMMISSIONING = "failed_commissioning",
  FAILED_DEPLOYMENT = "failed_deployment",
  FAILED_DISK_ERASING = "failed_disk_erasing",
  FAILED_ENTERING_RESCUE_MODE = "failed_entering_rescue_mode",
  FAILED_EXITING_RESCUE_MODE = "failed_exiting_rescue_mode",
  FAILED_RELEASING = "failed_releasing",
  FAILED_TESTING = "failed_testing",
  MISSING = "missing",
  NEW = "new",
  READY = "ready",
  RELEASING = "releasing",
  RESCUE_MODE = "rescue_mode",
  RESERVED = "reserved",
  RETIRED = "retired",
  TESTING = "testing",
}

export enum NodeActions {
  ABORT = "abort",
  ACQUIRE = "acquire",
  CHECK_POWER = "check-power",
  CLONE = "clone",
  COMMISSION = "commission",
  DELETE = "delete",
  DEPLOY = "deploy",
  EXIT_RESCUE_MODE = "exit-rescue-mode",
  IMPORT_IMAGES = "import-images",
  LOCK = "lock",
  MARK_BROKEN = "mark-broken",
  MARK_FIXED = "mark-fixed",
  OFF = "off",
  ON = "on",
  OVERRIDE_FAILED_TESTING = "override-failed-testing",
  POWER_CYCLE = "power-cycle", // TODO: Verify string with backend https://warthogs.atlassian.net/browse/MAASENG-4185
  RELEASE = "release",
  RESCUE_MODE = "rescue-mode",
  SET_POOL = "set-pool",
  SET_ZONE = "set-zone",
  SOFT_OFF = "soft-off",
  TAG = "tag",
  TEST = "test",
  UNLOCK = "unlock",
  UNTAG = "untag",
}

export enum TestStatusStatus {
  NONE = -1,
  PENDING = 0,
  RUNNING = 1,
  PASSED = 2,
  FAILED = 3,
}

export type TestStatus = {
  status: TestStatusStatus;
  pending: number;
  running: number;
  passed: number;
  failed: number;
};

/**
 * SimpleNode represents the intersection of Devices, Machines and Controllers
 */
export type SimpleNode = Model & {
  domain: ModelRef;
  hostname: string;
  fqdn: string;
  permissions: string[];
  system_id: string;
  tags: Tag[TagMeta.PK][];
};

/**
 * BaseNode represents the intersection of Machines and Controllers
 */
export type BaseNode = SimpleNode & {
  architecture: string;
  cpu_count: number;
  cpu_speed: number;
  cpu_test_status: TestStatus;
  description: string;
  distro_series: string;
  interface_test_status: TestStatus;
  locked: boolean;
  memory: number;
  memory_test_status: TestStatus;
  network_test_status: TestStatus;
  osystem: string;
  other_test_status: TestStatus;
  pool?: ModelRef;
  status: NodeStatus;
  status_message: string | null;
  status_code: NodeStatusCode;
  storage_test_status: TestStatus;
};

export type Node = Controller | Device | Machine;

export type NodeModel =
  | ControllerMeta.MODEL
  | DeviceMeta.MODEL
  | MachineMeta.MODEL;

export type NodeDetails = ControllerDetails | DeviceDetails | MachineDetails;

export type NetworkLink = Model & {
  ip_address?: string;
  mode: NetworkLinkMode;
  subnet_id: Subnet["id"];
};

export type DiscoveredIP = {
  ip_address: string;
  subnet_id: number;
};

export type NetworkInterfaceParams = {
  bridge_type?: BridgeType;
  bridge_stp?: boolean;
  bridge_fd?: number;
  mtu?: number;
  accept_ra?: boolean;
  autoconf?: boolean;
  bond_mode?: BondMode;
  bond_miimon?: number;
  bond_downdelay?: number;
  bond_updelay?: number;
  bond_lacp_rate?: BondLacpRate;
  bond_xmit_hash_policy?: BondXmitHashPolicy;
  bond_num_grat_arp?: number;
};

export type NetworkInterface = Model & {
  children: Model["id"][];
  discovered?: DiscoveredIP[] | null; // Only shown when machine is in ephemeral state.
  enabled: boolean;
  firmware_version: string | null;
  interface_speed: number;
  is_boot: boolean;
  link_connected: boolean;
  link_speed: number;
  links: NetworkLink[];
  mac_address: string;
  name: string;
  numa_node: number;
  params: NetworkInterfaceParams | null;
  parents: Model["id"][];
  product: string | null;
  sriov_max_vf: number;
  tags: string[];
  type: NetworkInterfaceTypes;
  vendor: string | null;
  vlan_id: VLAN[VLANMeta.PK];
};

export type Filesystem = Model & {
  fstype: string;
  is_format_fstype: boolean;
  label: string;
  mount_options: string | null;
  mount_point: string;
  used_for: string;
};

export type Partition = Model & {
  filesystem: Filesystem | null;
  name: string;
  path: string;
  size_human: string;
  size: number;
  tags: string[];
  type: string;
  used_for: string;
};

export type Disk = Model & {
  available_size_human: string;
  available_size: number;
  block_size: number;
  filesystem: Filesystem | null;
  firmware_version: string;
  is_boot: boolean;
  model: string;
  name: string;
  numa_node?: number;
  numa_nodes?: number[];
  parent?: {
    id: number;
    uuid: string;
    type: DiskTypes;
  };
  partition_table_type: string;
  partitions: Partition[] | null;
  path: string;
  serial: string;
  size_human: string;
  size: number;
  tags: string[];
  test_status: number;
  type: DiskTypes;
  used_for: string;
  used_size_human: string;
  used_size: number;
};

export type EventType = Model & {
  description: string;
  level: string;
  name: string;
};

export type NodeEvent = Omit<TimestampedModel, "updated"> & {
  description: string;
  type: EventType;
};

export type NodeDeviceRef = {
  fqdn: string;
  interfaces: NetworkInterface[];
};

export type GroupedStorage = {
  count: number;
  disk_type: string;
  size: number;
};

export type NodeIpAddress = {
  ip: string;
  is_boot: boolean;
};

// Node metadata is dynamic and depends on the specific hardware.
export type NodeMetadata = {
  chassis_serial?: string;
  chassis_type?: string;
  chassis_vendor?: string;
  chassis_version?: string;
  cpu_model?: string;
  mainboard_firmware_date?: string;
  mainboard_firmware_vendor?: string;
  mainboard_firmware_version?: string;
  mainboard_product?: string;
  mainboard_serial?: string;
  mainboard_vendor?: string;
  mainboard_version?: string;
  system_family?: string;
  system_product?: string;
  system_serial?: string;
  system_sku?: string;
  system_vendor?: string;
  system_version?: string;
};

export type NodeNumaNode = Model & {
  cores: number[];
  hugepages_set: {
    page_size: number;
    total: number;
  }[];
  index: number;
  memory: number;
};

// Power parameters are dynamic and depend on the power type of the node.
export type PowerParameter = string[] | number | string;

export type PowerParameters = Record<string, PowerParameter>;

export type SupportedFilesystem = {
  key: Filesystem["fstype"];
  ui: string;
};

export type NodeVlan = Model & {
  fabric_id: number;
  fabric_name: string;
  name: string;
};

export type WorkloadAnnotations = Record<string, string>;

export type BaseNodeActionParams = {
  system_id: Node["system_id"];
};

// Common params for methods that can accept a link.
export type LinkParams = {
  default_gateway?: boolean;
  ip_address?: NetworkLink["ip_address"];
  mode?: NetworkLinkMode;
  subnet?: Subnet["id"];
};

export type ScriptInputParam = Record<string, { url: string }>;

export type SetZoneParams = BaseNodeActionParams & {
  zone_id: ZoneResponse["id"];
};

export type TestParams = BaseNodeActionParams & {
  enable_ssh?: boolean;
  script_input?: ScriptInputParam;
  testing_scripts?: Script["name"][];
};

// On the API backend the update is processed by a form that handles all node
// types so this type must allow all possible parameters.
export type UpdateInterfaceParams = BaseNodeActionParams &
  LinkParams & {
    bridge_fd?: NetworkInterfaceParams["bridge_fd"];
    bridge_stp?: NetworkInterfaceParams["bridge_stp"];
    bond_downdelay?: NetworkInterfaceParams["bond_downdelay"];
    bond_lacp_rate?: NetworkInterfaceParams["bond_lacp_rate"];
    bond_miimon?: NetworkInterfaceParams["bond_miimon"];
    bond_mode?: NetworkInterfaceParams["bond_mode"];
    bond_num_grat_arp?: NetworkInterfaceParams["bond_num_grat_arp"];
    bond_updelay?: NetworkInterfaceParams["bond_updelay"];
    bond_xmit_hash_policy?: NetworkInterfaceParams["bond_xmit_hash_policy"];
    bridge_type?: NetworkInterfaceParams["bridge_type"];
    enabled?: NetworkInterface["enabled"];
    interface_id: NetworkInterface["id"];
    interface_speed?: NetworkInterface["interface_speed"];
    link_connected?: NetworkInterface["link_connected"];
    link_id?: NetworkLink["id"];
    link_speed?: NetworkInterface["link_speed"];
    mac_address?: NetworkInterface["mac_address"];
    name?: NetworkInterface["name"];
    numa_node?: NetworkInterface["numa_node"];
    parents?: NetworkInterface["parents"];
    tags?: NetworkInterface["tags"];
    vlan?: NetworkInterface["vlan_id"];
  };
