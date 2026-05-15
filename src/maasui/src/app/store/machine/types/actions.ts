import type {
  Machine,
  MachineStatus,
  FilterGroupKey,
  MachineStateListGroup,
  MachineDetails,
} from "./base";
import type { MachineMeta } from "./enum";

import type { ResourcePoolResponse, ZoneResponse } from "@/app/apiclient";
import type { Prettify } from "@/app/base/types";
import type { Domain } from "@/app/store/domain/types";
import type { Fabric } from "@/app/store/fabric/types";
import type { LicenseKeys } from "@/app/store/licensekeys/types";
import type { Pod } from "@/app/store/pod/types";
import type { Script, ScriptName } from "@/app/store/script/types";
import type { Space } from "@/app/store/space/types";
import type { Subnet } from "@/app/store/subnet/types";
import type { Tag, TagMeta } from "@/app/store/tag/types";
import type {
  DiskTypes,
  NetworkLinkMode,
  StorageLayout,
} from "@/app/store/types/enum";
import type { ModelRef } from "@/app/store/types/model";
import type {
  Node,
  BaseNodeActionParams,
  FetchNodeStatus,
  LinkParams,
  NetworkInterface,
  NetworkInterfaceParams,
  NetworkLink,
  NodeIpAddress,
  NodeVlan,
  PowerParameters,
  ScriptInputParam,
  SetZoneParams as NodeSetZoneParams,
  TestParams as NodeTestParams,
} from "@/app/store/types/node";

export type Action = {
  name: string;
  status: keyof MachineStatus;
};

export type ApplyStorageLayoutParams = {
  systemId: Machine[MachineMeta.PK];
  storageLayout: StorageLayout;
};

export type BaseMachineActionParams = Prettify<
  | BaseNodeActionParams
  | {
      system_id?: never;
      filter: FetchFilters;
      callId?: string;
    }
>;

export type CloneParams = BaseMachineActionParams & {
  system_id: Node["system_id"];
  filter: FetchFilters;
  interfaces: boolean;
  storage: boolean;
};

export type CommissionParams = BaseMachineActionParams & {
  commissioning_scripts?: Script["name"][];
  enable_ssh?: boolean;
  script_input?: ScriptInputParam;
  skip_bmc_config?: boolean;
  skip_networking?: boolean;
  skip_storage?: boolean;
  testing_scripts?: Script["name"][] | [ScriptName.NONE];
};

export type CreateBcacheParams = OptionalFilesystemParams & {
  blockId?: number;
  cacheMode: string;
  cacheSetId: number;
  name: string;
  partitionId?: number;
  systemId: Machine[MachineMeta.PK];
  tags?: string[];
};

export type CreateBondParams = LinkParams & {
  bond_downdelay?: NetworkInterfaceParams["bond_downdelay"];
  bond_lacp_rate?: NetworkInterfaceParams["bond_lacp_rate"];
  bond_miimon?: NetworkInterfaceParams["bond_miimon"];
  bond_mode?: NetworkInterfaceParams["bond_mode"];
  bond_num_grat_arp?: NetworkInterfaceParams["bond_num_grat_arp"];
  bond_updelay?: NetworkInterfaceParams["bond_updelay"];
  bond_xmit_hash_policy?: NetworkInterfaceParams["bond_xmit_hash_policy"];
  interface_speed?: NetworkInterface["interface_speed"];
  link_connected?: NetworkInterface["link_connected"];
  link_speed?: NetworkInterface["link_speed"];
  mac_address?: NetworkInterface["mac_address"];
  name?: NetworkInterface["name"];
  parents: NetworkInterface["parents"];
  system_id: Machine[MachineMeta.PK];
  tags?: NetworkInterface["tags"];
  vlan?: NetworkInterface["vlan_id"];
};

export type CreateBridgeParams = LinkParams & {
  bridge_fd?: NetworkInterfaceParams["bridge_fd"];
  bridge_stp?: NetworkInterfaceParams["bridge_stp"];
  bridge_type: NetworkInterfaceParams["bridge_type"];
  interface_speed?: NetworkInterface["interface_speed"];
  link_connected?: NetworkInterface["link_connected"];
  link_speed?: NetworkInterface["link_speed"];
  mac_address: NetworkInterface["mac_address"];
  name: NetworkInterface["name"];
  parents: NetworkInterface["parents"];
  system_id: Machine[MachineMeta.PK];
  tags?: NetworkInterface["tags"];
  vlan?: NetworkInterface["vlan_id"];
};

export type CreateCacheSetParams = {
  blockId?: number;
  partitionId?: number;
  systemId: Machine[MachineMeta.PK];
};

export type CreateLogicalVolumeParams = OptionalFilesystemParams & {
  name: string;
  size: number;
  systemId: Machine[MachineMeta.PK];
  tags?: string[];
  volumeGroupId: number;
};

export type CreateParams = {
  architecture?: Machine["architecture"];
  commission?: boolean;
  cpu_count?: Machine["cpu_count"];
  description?: Machine["description"];
  distro_series?: Machine["distro_series"];
  domain?: { name: Domain["name"] };
  ephemeral_deploy?: boolean;
  extra_macs: MachineDetails["extra_macs"];
  hostname?: Machine["hostname"];
  hwe_kernel?: string;
  install_rackd?: boolean;
  is_dpu?: boolean;
  license_key?: LicenseKeys["license_key"];
  memory?: Machine["memory"];
  min_hwe_kernel?: string;
  osystem?: Machine["osystem"];
  pool?: { name: ResourcePoolResponse["name"] };
  power_parameters: PowerParameters;
  power_type: Machine["power_type"];
  pxe_mac: Machine["pxe_mac"];
  swap_size?: string;
  zone?: { name: ZoneResponse["name"] };
};

export type CreatePartitionParams = OptionalFilesystemParams & {
  blockId: number;
  partitionSize: number;
  systemId: Machine[MachineMeta.PK];
};

export type CreatePhysicalParams = LinkParams & {
  enabled?: NetworkInterface["enabled"];
  interface_speed?: NetworkInterface["interface_speed"];
  ip_assignment?: "dynamic" | "external" | "static";
  link_connected?: NetworkInterface["link_connected"];
  link_speed?: NetworkInterface["link_speed"];
  mac_address: NetworkInterface["mac_address"];
  name?: NetworkInterface["name"];
  numa_node?: NetworkInterface["numa_node"];
  system_id: Machine[MachineMeta.PK];
  tags?: NetworkInterface["tags"];
  vlan?: NetworkInterface["vlan_id"];
};

export type CreateRaidParams = OptionalFilesystemParams & {
  blockDeviceIds?: number[];
  level: DiskTypes;
  name: string;
  partitionIds?: number[];
  spareBlockDeviceIds?: number[];
  sparePartitionIds?: number[];
  systemId: Machine[MachineMeta.PK];
  tags?: string[];
};

export type CreateVlanParams = LinkParams & {
  interface_speed?: NetworkInterface["interface_speed"];
  link_connected?: NetworkInterface["link_connected"];
  link_speed?: NetworkInterface["link_speed"];
  parent: NetworkInterface["parents"][0];
  system_id: Machine[MachineMeta.PK];
  tags?: NetworkInterface["tags"];
  vlan?: NetworkInterface["vlan_id"];
};

export type CreateVmfsDatastoreParams = {
  blockDeviceIds?: number[];
  name: string;
  partitionIds?: number[];
  systemId: Machine[MachineMeta.PK];
};

export type CreateVolumeGroupParams = {
  blockDeviceIds?: number[];
  name: string;
  partitionIds?: number[];
  systemId: Machine[MachineMeta.PK];
};

export type DeleteCacheSetParams = {
  cacheSetId: number;
  systemId: Machine[MachineMeta.PK];
};

export type DeleteDiskParams = {
  blockId: number;
  systemId: Machine[MachineMeta.PK];
};

export type DeleteFilesystemParams = {
  blockDeviceId?: number;
  filesystemId: number;
  partitionId?: number;
  systemId: Machine[MachineMeta.PK];
};

export type DeleteInterfaceParams = {
  interfaceId: NetworkInterface["id"];
  systemId: Machine[MachineMeta.PK];
};

export type DeletePartitionParams = {
  partitionId: number;
  systemId: Machine[MachineMeta.PK];
};

export type DeleteVolumeGroupParams = {
  systemId: Machine[MachineMeta.PK];
  volumeGroupId: number;
};

export type DeployParams = BaseMachineActionParams & {
  distro_series?: Machine["distro_series"];
  enable_hw_sync?: boolean;
  ephemeral_deploy?: boolean;
  hwe_kernel?: string;
  install_kvm?: boolean;
  osystem?: Machine["osystem"];
  register_vmhost?: boolean;
  user_data?: string;
  enable_kernel_crash_dump?: boolean;
};

export enum FetchSortDirection {
  Ascending = "ascending",
  Descending = "descending",
}

type ArrayOrValue<T> = { [P in keyof T]: T[P] | T[P][] };

type Filters = {
  [FilterGroupKey.AgentName]: string;
  [FilterGroupKey.Arch]: Machine["architecture"];
  [FilterGroupKey.CpuCount]: Machine["cpu_count"];
  [FilterGroupKey.CpuSpeed]: MachineDetails["cpu_speed"];
  [FilterGroupKey.Description]: Machine["description"];
  [FilterGroupKey.DistroSeries]: Machine["distro_series"];
  [FilterGroupKey.Domain]: Domain["name"];
  [FilterGroupKey.ErrorDescription]: Machine["error_description"];
  [FilterGroupKey.FabricClasses]: Fabric["class_type"];
  [FilterGroupKey.Fabrics]: Machine["fabrics"][0];
  [FilterGroupKey.FreeText]: string;
  [FilterGroupKey.Hostname]: Machine["hostname"];
  [FilterGroupKey.IpAddresses]: NodeIpAddress["ip"];
  [FilterGroupKey.LinkSpeed]: MachineDetails["link_speeds"][0];
  [FilterGroupKey.MacAddress]: NetworkInterface["mac_address"];
  [FilterGroupKey.Mem]: Machine["memory"];
  [FilterGroupKey.Osystem]: Machine["osystem"];
  [FilterGroupKey.Owner]: Machine["owner"];
  [FilterGroupKey.Parent]: Node["system_id"];
  [FilterGroupKey.Pod]: ModelRef["name"];
  [FilterGroupKey.PodType]: Pod["type"];
  [FilterGroupKey.Pool]: ResourcePoolResponse["name"];
  [FilterGroupKey.Spaces]: Space["name"];
  [FilterGroupKey.Status]: FetchNodeStatus;
  [FilterGroupKey.Subnets]: Subnet["name"];
  [FilterGroupKey.Id]: Machine["system_id"];
  [FilterGroupKey.Tags]: Tag["name"];
  [FilterGroupKey.Vlans]: NodeVlan["name"];
  [FilterGroupKey.Workloads]: string;
  [FilterGroupKey.Zone]: Machine["zone"]["name"];
};

type ExcludeFilters = {
  [FilterGroupKey.NotArch]: Filters[FilterGroupKey.Arch];
  [FilterGroupKey.NotCpuCount]: Filters[FilterGroupKey.CpuCount];
  [FilterGroupKey.NotCpuSpeed]: Filters[FilterGroupKey.CpuSpeed];
  [FilterGroupKey.NotDistroSeries]: Filters[FilterGroupKey.DistroSeries];
  [FilterGroupKey.NotFabricClasses]: Filters[FilterGroupKey.FabricClasses];
  [FilterGroupKey.NotFabrics]: Filters[FilterGroupKey.Fabrics];
  [FilterGroupKey.NotInPool]: Filters[FilterGroupKey.Pool];
  [FilterGroupKey.NotInZone]: Filters[FilterGroupKey.Zone];
  [FilterGroupKey.NotIpAddresses]: Filters[FilterGroupKey.IpAddresses];
  [FilterGroupKey.NotLinkSpeed]: Filters[FilterGroupKey.LinkSpeed];
  [FilterGroupKey.NotMem]: Filters[FilterGroupKey.Mem];
  [FilterGroupKey.NotOsystem]: Filters[FilterGroupKey.Osystem];
  [FilterGroupKey.NotOwner]: Filters[FilterGroupKey.Owner];
  [FilterGroupKey.NotPod]: Filters[FilterGroupKey.Pod];
  [FilterGroupKey.NotPodType]: Filters[FilterGroupKey.PodType];
  [FilterGroupKey.NotSubnets]: Filters[FilterGroupKey.Subnets];
  [FilterGroupKey.NotId]: Filters[FilterGroupKey.Id];
  [FilterGroupKey.NotTags]: Filters[FilterGroupKey.Tags];
  [FilterGroupKey.NotVlans]: Filters[FilterGroupKey.Vlans];
};

export type FetchFilters = Partial<
  ArrayOrValue<ExcludeFilters> & ArrayOrValue<Filters>
>;

export enum FetchGroupKey {
  AddressTtl = "address_ttl",
  AgentName = "agent_name",
  Architecture = "architecture",
  BiosBootMethod = "bios_boot_method",
  Bmc = "bmc",
  BmcId = "bmc_id",
  BootClusterIp = "boot_cluster_ip",
  BootDisk = "boot_disk",
  BootDiskId = "boot_disk_id",
  BootInterface = "boot_interface",
  BootInterfaceId = "boot_interface_id",
  Children = "children",
  Connections = "connections",
  Controllerinfo = "controllerinfo",
  CpuCount = "cpu_count",
  CpuSpeed = "cpu_speed",
  Created = "created",
  CurrentCommissioningScriptSet = "current_commissioning_script_set",
  CurrentCommissioningScriptSetId = "current_commissioning_script_set_id",
  CurrentConfig = "current_config",
  CurrentConfigId = "current_config_id",
  CurrentInstallationScriptSet = "current_installation_script_set",
  CurrentInstallationScriptSetId = "current_installation_script_set_id",
  CurrentTestingScriptSet = "current_testing_script_set",
  CurrentTestingScriptSetId = "current_testing_script_set_id",
  DefaultUser = "default_user",
  Description = "description",
  Dhcpsnippet = "dhcpsnippet",
  Discovery = "discovery",
  DistroSeries = "distro_series",
  DnsProcess = "dns_process",
  DnsProcessId = "dns_process_id",
  Domain = "domain",
  DomainId = "domain_id",
  Dynamic = "dynamic",
  EnableHwSync = "enable_hw_sync",
  EnableSsh = "enable_ssh",
  EphemeralDeploy = "ephemeral_deploy",
  Error = "error",
  ErrorDescription = "error_description",
  Event = "event",
  GatewayLinkIpv4 = "gateway_link_ipv4",
  GatewayLinkIpv4Id = "gateway_link_ipv4_id",
  GatewayLinkIpv6 = "gateway_link_ipv6",
  GatewayLinkIpv6Id = "gateway_link_ipv6_id",
  HardwareUuid = "hardware_uuid",
  Hostname = "hostname",
  HweKernel = "hwe_kernel",
  Id = "id",
  InstallKvm = "install_kvm",
  InstallRackd = "install_rackd",
  InstancePowerParameters = "instance_power_parameters",
  LastAppliedStorageLayout = "last_applied_storage_layout",
  LastImageSync = "last_image_sync",
  LastSync = "last_sync",
  LicenseKey = "license_key",
  Locked = "locked",
  ManagingProcess = "managing_process",
  ManagingProcessId = "managing_process_id",
  Memory = "memory",
  MinHweKernel = "min_hwe_kernel",
  Netboot = "netboot",
  NodeType = "node_type",
  Nodeconfig = "nodeconfig",
  Nodekey = "nodekey",
  Nodemetadata = "nodemetadata",
  Nodeuserdata = "nodeuserdata",
  NumaNodesCount = "numa_nodes_count",
  Numanode = "numanode",
  None = "",
  Osystem = "osystem",
  Owner = "owner",
  OwnerId = "owner_id",
  Ownerdata = "ownerdata",
  Parent = "parent",
  ParentId = "parent_id",
  PhysicalDiskCount = "physical_disk_count",
  Podhints = "podhints",
  Pod = "pod",
  PodType = "pod_type",
  Pool = "pool",
  PoolId = "pool_id",
  PowerState = "power_state",
  PowerStateQueried = "power_state_queried",
  PowerStateUpdated = "power_state_updated",
  PreviousStatus = "previous_status",
  Processes = "processes",
  Rdns = "rdns",
  RegisterVmhost = "register_vmhost",
  RoutableBmcRelationships = "routable_bmc_relationships",
  RoutableBmcs = "routable_bmcs",
  Scriptset = "scriptset",
  Service = "service",
  SkipNetworking = "skip_networking",
  SkipStorage = "skip_storage",
  SriovSupport = "sriov_support",
  Status = "status",
  StatusEventDescription = "status_event_description",
  StatusEventTypeDescription = "status_event_type_description",
  StatusExpires = "status_expires",
  SwapSize = "swap_size",
  SyncInterval = "sync_interval",
  SystemId = "system_id",
  Tags = "tags",
  TotalStorage = "total_storage",
  Updated = "updated",
  Url = "url",
  Virtualmachine = "virtualmachine",
  Zone = "zone",
  ZoneId = "zone_id",
}

// subset of FetchGroupKey keys used for grouping in the UI
export enum FetchGroupByKey {
  Status = FetchGroupKey.Status,
  Owner = FetchGroupKey.Owner,
  Pool = FetchGroupKey.Pool,
  Architecture = FetchGroupKey.Architecture,
  Domain = FetchGroupKey.Domain,
  Parent = FetchGroupKey.Parent,
  Pod = FetchGroupKey.Pod,
  PodType = FetchGroupKey.PodType,
  PowerState = FetchGroupKey.PowerState,
  Zone = FetchGroupKey.Zone,
}

export type FetchParams = {
  filter?: FetchFilters | null;
  group_key?: FetchGroupKey | null;
  group_collapsed?: MachineStateListGroup["value"][] | null;
  page_size?: number;
  page_number?: number;
  sort_key?: FetchGroupKey | string | null;
  sort_direction?: FetchSortDirection | null;
};

export type GetSummaryXmlParams = {
  systemId: Machine[MachineMeta.PK];
  fileId: string;
};

export type GetSummaryYamlParams = {
  systemId: Machine[MachineMeta.PK];
  fileId: string;
};

export type LinkSubnetParams = {
  interface_id: NetworkInterface["id"];
  ip_address?: NetworkLink["ip_address"];
  link_id?: NetworkLink["id"];
  mode: NetworkLinkMode;
  subnet?: Subnet["id"];
  system_id: Machine[MachineMeta.PK];
};

export type MarkBrokenParams = BaseMachineActionParams & {
  message?: string;
};

export type MountSpecialParams = {
  fstype: string;
  mountOptions: string;
  mountPoint: string;
  systemId: Machine[MachineMeta.PK];
};

export type OverrideFailedTesting = BaseMachineActionParams & {
  suppress_failed_script_results?: boolean;
};

export type OptionalFilesystemParams = {
  fstype?: string;
  mountOptions?: string;
  mountPoint?: string;
};

export type ReleaseParams = BaseMachineActionParams & {
  erase?: boolean;
  quick_erase?: boolean;
  secure_erase?: boolean;
};

export type SetBootDiskParams = {
  blockId: number;
  systemId: Machine[MachineMeta.PK];
};

export type SetPoolParams = BaseMachineActionParams & {
  pool_id: ResourcePoolResponse["id"];
};

export type SetZoneParams = BaseMachineActionParams &
  Omit<NodeSetZoneParams, "system_id">;

export type TagParams = BaseMachineActionParams & {
  tags?: Tag[TagMeta.PK][];
};

export type TestParams = BaseMachineActionParams &
  Omit<NodeTestParams, "system_id">;

export type UnlinkSubnetParams = {
  interfaceId: NetworkInterface["id"];
  linkId: NetworkLink["id"];
  systemId: Machine[MachineMeta.PK];
};

export type UnmountSpecialParams = {
  mountPoint: string;
  systemId: Machine[MachineMeta.PK];
};

export type UntagParams = BaseMachineActionParams & {
  tags: Tag[TagMeta.PK][];
};

export type UpdateDiskParams = OptionalFilesystemParams & {
  blockId: number;
  name?: string;
  systemId: Machine[MachineMeta.PK];
  tags?: string[];
};

export type UpdateFilesystemParams = OptionalFilesystemParams & {
  blockId?: number;
  partitionId?: number;
  systemId: Machine[MachineMeta.PK];
  tags?: string[];
};

export type UpdateParams = Partial<CreateParams> & {
  [MachineMeta.PK]: Machine[MachineMeta.PK];
  tags?: Machine["tags"];
};

export type UpdateVmfsDatastoreParams = {
  blockDeviceIds?: number[];
  name?: string;
  partitionIds?: number[];
  systemId: Machine[MachineMeta.PK];
  vmfsDatastoreId?: number;
};
