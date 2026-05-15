import type {
  ControllerInstallType,
  ControllerMeta,
  ControllerVersionIssues,
  ImageSyncStatus,
} from "./enum";

import type { APIError } from "@/app/base/types";
import type { CertificateMetadata, PowerType } from "@/app/store/general/types";
import type { PowerState, StorageLayout } from "@/app/store/types/enum";
import type {
  ModelRef,
  TimestampFields,
  UtcDatetime,
} from "@/app/store/types/model";
import type {
  NodeActions,
  BaseNode,
  NodeType,
  NodeTypeDisplay,
  NodeLinkType,
  Disk,
  TestStatus,
  NodeEvent,
  GroupedStorage,
  NetworkInterface,
  NodeIpAddress,
  NodeMetadata,
  NodeNumaNode,
  PowerParameters,
  NodeStatus,
  Filesystem,
  SupportedFilesystem,
  NodeVlan,
  WorkloadAnnotations,
  NodeDeviceRef,
} from "@/app/store/types/node";
import type { EventError, GenericState } from "@/app/store/types/state";
import type { VLAN, VLANMeta } from "@/app/store/vlan/types";

export type ControllerVersionInfo = {
  snap_revision?: string;
  version: string;
};

export type ControllerVersions = {
  current: ControllerVersionInfo;
  install_type?: ControllerInstallType;
  origin: string;
  snap_cohort?: string;
  up_to_date: boolean;
  update?: ControllerVersionInfo;
  issues: ControllerVersionIssues[];
};

export type ControllerVlansHA = {
  false: number;
  true: number;
};

export type ControllerActions =
  | NodeActions.DELETE
  | NodeActions.IMPORT_IMAGES
  | NodeActions.OFF
  | NodeActions.ON
  | NodeActions.OVERRIDE_FAILED_TESTING
  | NodeActions.SET_ZONE
  | NodeActions.TEST;

export type BaseController = BaseNode & {
  actions: ControllerActions[];
  last_image_sync: UtcDatetime;
  link_type: NodeLinkType.CONTROLLER;
  node_type_display:
    | NodeTypeDisplay.RACK_CONTROLLER
    | NodeTypeDisplay.REGION_AND_RACK_CONTROLLER
    | NodeTypeDisplay.REGION_CONTROLLER;
  node_type:
    | typeof NodeType.RACK_CONTROLLER
    | typeof NodeType.REGION_AND_RACK_CONTROLLER
    | typeof NodeType.REGION_CONTROLLER;
  service_ids: number[];
  vault_configured?: boolean;
  versions: ControllerVersions | null;
  vlans_ha?: ControllerVlansHA;
};

export type ControllerDetails = BaseController &
  TimestampFields & {
    bios_boot_method: string;
    bmc: number;
    boot_disk: Disk | null;
    certificate?: CertificateMetadata;
    commissioning_start_time: string;
    commissioning_status: TestStatus;
    current_commissioning_script_set: number;
    current_installation_script_set: number;
    current_testing_script_set: number;
    default_user: string;
    detected_storage_layout: StorageLayout;
    devices: NodeDeviceRef[];
    dhcp_on: boolean;
    disks: Disk[];
    dynamic: boolean;
    ephemeral_deploy: boolean;
    error_description: string;
    error: string;
    events: NodeEvent[];
    grouped_storages: GroupedStorage[];
    hardware_uuid: string | null;
    has_logs: boolean;
    hwe_kernel: string | null;
    install_kvm: boolean;
    install_rackd: boolean;
    installation_start_time: string;
    installation_status: number;
    interfaces: NetworkInterface[];
    ip_addresses: NodeIpAddress[];
    last_applied_storage_layout: StorageLayout;
    license_key: string | null;
    metadata: NodeMetadata;
    min_hwe_kernel: string | null;
    numa_nodes: NodeNumaNode[];
    on_network: boolean;
    owner: string;
    physical_disk_count: number;
    power_bmc_node_count: number;
    power_parameters: PowerParameters;
    power_state: PowerState;
    power_type: PowerType["name"];
    previous_status: NodeStatus;
    pxe_mac?: string;
    register_vmhost: boolean;
    show_os_info: boolean;
    special_filesystems: Filesystem[];
    storage_layout_issues: string[];
    storage_tags: string[];
    storage: number;
    supported_filesystems: SupportedFilesystem[];
    swap_size: number | null;
    testing_start_time: string;
    testing_status: TestStatus;
    vlan_ids: VLAN[VLANMeta.PK][];
    vlan?: NodeVlan | null;
    workload_annotations: WorkloadAnnotations;
    zone: ModelRef;
  };

export type Controller = BaseController | ControllerDetails;

export type ControllerStatus = {
  checkingImages: boolean;
  deleting: boolean;
  gettingSummaryXml: boolean;
  gettingSummaryYaml: boolean;
  importingImages: boolean;
  turningOff: boolean;
  turningOn: boolean;
  overridingFailedTesting: boolean;
  settingZone: boolean;
  testing: boolean;
};

export type ControllerStatuses = Record<
  Controller[ControllerMeta.PK],
  ControllerStatus
>;

export type ImageSyncStatuses = Record<
  Controller[ControllerMeta.PK],
  ImageSyncStatus
>;

export type ControllerState = GenericState<Controller, APIError> & {
  active: Controller[ControllerMeta.PK] | null;
  eventErrors: EventError<Controller, APIError, ControllerMeta.PK>[];
  imageSyncStatuses: ImageSyncStatuses;
  selected: Controller[ControllerMeta.PK][];
  statuses: ControllerStatuses;
};
