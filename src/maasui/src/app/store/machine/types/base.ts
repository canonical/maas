import type { FetchFilters, FetchGroupKey, FetchParams } from "./actions";
import type { MachineMeta } from "./enum";

import type { ActionState, APIError, Seconds } from "@/app/base/types";
import type { CloneError } from "@/app/machines/components/MachineForms/MachineActionFormWrapper/CloneForm/CloneResults/CloneResults";
import type { CertificateMetadata, PowerType } from "@/app/store/general/types";
import type { PowerState, StorageLayout } from "@/app/store/types/enum";
import type {
  ModelRef,
  TimestampFields,
  UtcDatetime,
} from "@/app/store/types/model";
import type {
  BaseNode,
  Disk,
  Filesystem,
  GroupedStorage,
  NetworkInterface,
  NodeActions,
  NodeDeviceRef,
  NodeEvent,
  NodeIpAddress,
  NodeLinkType,
  NodeMetadata,
  NodeNumaNode,
  NodeTypeDisplay,
  NodeVlan,
  PowerParameters,
  SupportedFilesystem,
  TestStatus,
  WorkloadAnnotations,
} from "@/app/store/types/node";
import type { EventError, GenericState } from "@/app/store/types/state";

export type MachineActions = Exclude<NodeActions, NodeActions.IMPORT_IMAGES>;

// BaseMachine is returned from the server when using "machine.list", and is
// used in the machine list. This type is missing some properties due to an
// optimisation on the backend to reduce the amount of database queries on list
// pages.
export type BaseMachine = Omit<
  BaseNode,
  "cpu_speed" | "interface_test_status"
> & {
  actions: MachineActions[];
  ephemeral_deploy: boolean;
  error_description: string;
  extra_macs: string[];
  fabrics: string[];
  ip_addresses: NodeIpAddress[] | null;
  link_type: NodeLinkType.MACHINE;
  owner: string;
  physical_disk_count: number;
  parent: string | null; // `parent` is a `system_id`
  pod: ModelRef | null;
  pool: ModelRef;
  power_state: PowerState;
  power_type: PowerType["name"] | "" | null;
  pxe_mac?: string;
  spaces: string[];
  storage: number;
  testing_status: TestStatus["status"];
  vlan: NodeVlan | null;
  zone: ModelRef;
};

// MachineDetails returned from the server when using "machine.get", and is
// used in the machine details pages.
export type MachineDetails = BaseMachine &
  HardwareSyncFields &
  TimestampFields & {
    bios_boot_method: string;
    bmc: number;
    boot_disk: Disk | null;
    certificate?: CertificateMetadata;
    commissioning_start_time: UtcDatetime;
    commissioning_status: TestStatus;
    cpu_speed: BaseNode["cpu_speed"];
    cpu_test_status: TestStatus;
    current_commissioning_script_set: number;
    current_installation_script_set: number;
    current_testing_script_set: number;
    detected_storage_layout: StorageLayout;
    devices: NodeDeviceRef[];
    dhcp_on: boolean;
    disks: Disk[];
    enable_kernel_crash_dump: boolean;
    error: string;
    events: NodeEvent[];
    grouped_storages: GroupedStorage[];
    hardware_uuid: string;
    has_logs: boolean;
    hwe_kernel: string;
    installation_status: number;
    interface_test_status: TestStatus;
    interfaces: NetworkInterface[];
    is_dpu: boolean;
    license_key: string;
    link_speeds: number[];
    memory_test_status: TestStatus;
    metadata: NodeMetadata;
    min_hwe_kernel: string;
    network_test_status: TestStatus;
    node_type: number;
    node_type_display: NodeTypeDisplay.MACHINE;
    numa_nodes: NodeNumaNode[];
    numa_nodes_count: number;
    on_network: boolean;
    other_test_status: TestStatus;
    permissions: string[];
    power_bmc_node_count: number;
    power_parameters: PowerParameters;
    show_os_info: boolean;
    special_filesystems: Filesystem[];
    sriov_support: boolean;
    storage_layout_issues: string[];
    storage_tags: string[];
    storage_test_status: TestStatus;
    subnets: string[];
    supported_filesystems: SupportedFilesystem[];
    swap_size: number | null;
    workload_annotations: WorkloadAnnotations;
  };

type HardwareSyncFields =
  | {
      enable_hw_sync: false;
    }
  | {
      enable_hw_sync: true;
      last_sync: UtcDatetime;
      next_sync: UtcDatetime;
      is_sync_healthy: boolean;
      sync_interval: Seconds;
    };

// Depending on where the user has navigated in the app, machines in state can
// either be of type BaseMachine or MachineDetails.
export type Machine = BaseMachine | MachineDetails;

export type MachineStatus = {
  aborting: boolean;
  acquiring: boolean;
  applyingStorageLayout: boolean;
  checkingPower: boolean;
  cloning: boolean;
  creatingBcache: boolean;
  creatingBond: boolean;
  creatingBridge: boolean;
  creatingCacheSet: boolean;
  creatingLogicalVolume: boolean;
  creatingPartition: boolean;
  creatingPhysical: boolean;
  creatingRaid: boolean;
  creatingVlan: boolean;
  creatingVmfsDatastore: boolean;
  creatingVolumeGroup: boolean;
  commissioning: boolean;
  deleting: boolean;
  deletingCacheSet: boolean;
  deletingDisk: boolean;
  deletingFilesystem: boolean;
  deletingInterface: boolean;
  deletingPartition: boolean;
  deletingVolumeGroup: boolean;
  deploying: boolean;
  enteringRescueMode: boolean;
  exitingRescueMode: boolean;
  gettingSummaryXml: boolean;
  gettingSummaryYaml: boolean;
  linkingSubnet: boolean;
  locking: boolean;
  markingBroken: boolean;
  markingFixed: boolean;
  mountingSpecial: boolean;
  overridingFailedTesting: boolean;
  releasing: boolean;
  settingBootDisk: boolean;
  settingPool: boolean;
  settingZone: boolean;
  tagging: boolean;
  testing: boolean;
  turningOff: boolean;
  turningOn: boolean;
  unlocking: boolean;
  unlinkingSubnet: boolean;
  unmountingSpecial: boolean;
  unsubscribing: boolean;
  untagging: boolean;
  updatingDisk: boolean;
  updatingFilesystem: boolean;
  updatingInterface: boolean;
  updatingVmfsDatastore: boolean;
};

export type MachineActionStatus = {
  errors: APIError;
  failed_system_ids: Machine["system_id"][];
  failure_details: Partial<Record<string, Machine["system_id"][]>>;
  success_count: number;
} | null;

export type MachineStatuses = Record<Machine[MachineMeta.PK], MachineStatus>;

export type MachineStateDetailsItem = {
  errors: APIError;
  loaded: boolean;
  loading: boolean;
  system_id: Machine[MachineMeta.PK];
};

export type MachineStateDetails = Record<string, MachineStateDetailsItem>;

export type FilterGroupOptionType = boolean | number | string;

export type FilterGroupOption<K = FilterGroupOptionType> = {
  key: K;
  label: string;
};

export type MachineStateListGroup = {
  collapsed: boolean;
  count: number | null;
  items: Machine[MachineMeta.PK][];
  name: FilterGroupOption["label"] | null;
  value: FilterGroupOption["key"] | null;
};

type MachineQuery = {
  // parameters used to fetch the list
  params: FetchParams | null;
  refetching: boolean;
  fetchedAt: number | null;
  refetchedAt: number | null;
};

export type MachineStateList = MachineQuery & {
  count: number | null;
  cur_page: number | null;
  errors: APIError;
  groups: MachineStateListGroup[] | null;
  loaded: boolean;
  loading: boolean;
  stale: boolean;
  num_pages: number | null;
};

export type MachineStateLists = Record<string, MachineStateList>;

export enum FilterGroupType {
  Bool = "bool",
  Dict = "dict[str,str]",
  Float = "float",
  FloatList = "list[float]",
  Int = "int",
  IntList = "list[int]",
  String = "str",
  StringList = "list[str]",
}

export enum FilterGroupKey {
  AgentName = "agent_name",
  Arch = "arch",
  CpuCount = "cpu_count",
  CpuSpeed = "cpu_speed",
  DeploymentTarget = "deployment_target",
  Description = "description",
  DistroSeries = "distro_series",
  Domain = "domain",
  ErrorDescription = "error_description",
  FabricClasses = "fabric_classes",
  Fabrics = "fabrics",
  FreeText = "free_text",
  Hostname = "hostname",
  Id = "id",
  IpAddresses = "ip_addresses",
  LinkSpeed = "link_speed",
  MacAddress = "mac_address",
  Mem = "mem",
  NotArch = "not_arch",
  NotCpuCount = "not_cpu_count",
  NotCpuSpeed = "not_cpu_speed",
  NotDistroSeries = "not_distro_series",
  NotFabricClasses = "not_fabric_classes",
  NotFabrics = "not_fabrics",
  NotId = "not_id",
  NotInPool = "not_in_pool",
  NotInZone = "not_in_zone",
  NotIpAddresses = "not_ip_addresses",
  NotLinkSpeed = "not_link_speed",
  NotMem = "not_mem",
  NotOsystem = "not_osystem",
  NotOwner = "not_owner",
  NotPod = "not_pod",
  NotPodType = "not_pod_type",
  NotSubnets = "not_subnets",
  NotTags = "not_tags",
  NotVlans = "not_vlans",
  Osystem = "osystem",
  Owner = "owner",
  Parent = "parent",
  Pod = "pod",
  PodType = "pod_type",
  Pool = "pool",
  Spaces = "spaces",
  Status = "status",
  Subnets = "subnets",
  Tags = "tags",
  Vlans = "vlans",
  Workloads = "workloads",
  Zone = "zone",
}

export type FilterGroup = {
  errors: APIError;
  key: FilterGroupKey;
  label: string;
  loaded: boolean;
  loading: boolean;
  dynamic: boolean;
  for_grouping: boolean;
} & (
  | {
      options: FilterGroupOption<number>[] | null;
      type:
        | FilterGroupType.Float
        | FilterGroupType.FloatList
        | FilterGroupType.Int
        | FilterGroupType.IntList;
    }
  | {
      options: FilterGroupOption<string>[] | null;
      type:
        | FilterGroupType.Dict
        | FilterGroupType.String
        | FilterGroupType.StringList;
    }
  | { options: FilterGroupOption<boolean>[] | null; type: FilterGroupType.Bool }
);

export type MachineEventErrors = CloneError;

export type MachineStateCount = MachineQuery & {
  count: number | null;
  errors: APIError;
  loaded: boolean;
  loading: boolean;
  stale: boolean;
};

export type MachineStateCounts = Record<string, MachineStateCount>;

export type SelectedMachines =
  | {
      items?: Machine[MachineMeta.PK][];
      groups?: MachineStateListGroup["value"][];
      grouping?: FetchGroupKey | null;
    }
  | { filter: FetchFilters };

export type MachineStateActions = Record<string, ActionState>;

export type MachineState = GenericState<Machine, APIError> & {
  actions: MachineStateActions;
  active: Machine[MachineMeta.PK] | null;
  counts: MachineStateCounts;
  details: MachineStateDetails;
  eventErrors: EventError<
    Machine,
    APIError<MachineEventErrors>,
    MachineMeta.PK
  >[];
  filters: FilterGroup[];
  filtersLoaded: boolean;
  filtersLoading: boolean;
  lists: MachineStateLists;
  selected: SelectedMachines | null;
  statuses: MachineStatuses;
};

export type StorageLayoutOption = {
  label: string;
  sentenceLabel: string;
  value: StorageLayout;
};
