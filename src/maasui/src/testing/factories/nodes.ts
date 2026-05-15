import { define, extend, random, sequence } from "cooky-cutter";

import { timestamp } from "./general";
import { model, modelRef, timestampedModel } from "./model";

import type {
  Controller,
  ControllerDetails,
  ControllerVersionInfo,
  ControllerVersions,
  ControllerVlansHA,
} from "@/app/store/controller/types";
import type {
  Device,
  DeviceDetails,
  DeviceNetworkInterface,
} from "@/app/store/device/types";
import { DeviceIpAssignment } from "@/app/store/device/types";
import type { Machine, MachineDetails } from "@/app/store/machine/types";
import {
  FilterGroupKey,
  FilterGroupType,
} from "@/app/store/machine/types/base";
import type { FilterGroup, BaseMachine } from "@/app/store/machine/types/base";
import { PodType } from "@/app/store/pod/constants";
import type {
  Pod,
  PodDetails,
  PodMemoryResource,
  PodNetworkInterface,
  PodNuma,
  PodNumaHugepageMemory,
  PodNumaMemory,
  PodNumaResource,
  PodPowerParameters,
  PodProject,
  PodResource,
  PodResources,
  PodStoragePool,
  PodStoragePoolResource,
  PodVM,
  PodVmCount,
} from "@/app/store/pod/types";
import {
  NetworkLinkMode,
  NetworkInterfaceTypes,
  DiskTypes,
  PowerState,
  StorageLayout,
} from "@/app/store/types/enum";
import type { Model, TimestampedModel } from "@/app/store/types/model";
import type {
  DiscoveredIP,
  NetworkInterface,
  NetworkLink,
  BaseNode,
  SimpleNode,
  TestStatus,
  NodeEvent,
  Disk,
  EventType,
  Filesystem,
  NodeNumaNode,
  Partition,
  NodeDeviceRef,
  NodeIpAddress,
} from "@/app/store/types/node";
import {
  NodeLinkType,
  NodeStatus,
  NodeType,
  NodeTypeDisplay,
} from "@/app/store/types/node";

export const testStatus = define<TestStatus>({
  status: 0,
  pending: 0,
  running: 0,
  passed: 0,
  failed: 0,
});

const actions = () => [];
const architectures = () => ["amd64/generic", "i386"];
const extra_macs = () => [];
const capabilities = () => [
  "composable",
  "dynamic_local_storage",
  "over_commit",
  "storage_pools",
];
const fabrics = () => [];
const ip_addresses = () => [];
const link_speeds = () => [];
const permissions = () => ["edit", "delete", "compose"];
const service_ids = () => [];
const spaces = () => [];
const storage_pools = () => [podStoragePool(), podStoragePool()];
const storage_tags = () => [];
const subnets = () => [];
const tags = () => [];

export const simpleNode = extend<Model, SimpleNode>(model, {
  domain: modelRef,
  hostname: (i: number) => `test-machine-${i}`,
  fqdn: (i: number) => `test-machine-${i}.maas`,
  permissions,
  system_id: () => random().toString(),
  tags,
});

export const nodeDisk = extend<Model, Disk>(model, {
  is_boot: true,
  name: "sda",
  tags: () => [],
  type: DiskTypes.PHYSICAL,
  path: "/dev/disk/by-dname/sda",
  size: 100000000000,
  size_human: "100 GB",
  used_size: 40000000000,
  used_size_human: "40 GB",
  available_size: 60000000000,
  available_size_human: "600 GB",
  block_size: 512,
  model: "QEMU HARDDISK",
  serial: "lxd_root",
  firmware_version: "2.5+",
  partition_table_type: "GPT",
  used_for: "GPT partitioned with 2 partitions",
  filesystem: null,
  partitions: () => [],
  numa_node: 0,
  test_status: 0,
});

export const nodeFilesystem = extend<Model, Filesystem>(model, {
  fstype: "fat32",
  is_format_fstype: true,
  label: "efi",
  mount_options: "abc",
  mount_point: "/boot/efi",
  used_for: "fat32 formatted filesystem mounted at /boot/efi",
});

export const nodePartition = extend<Model, Partition>(model, {
  filesystem: null,
  name: "sda-part1",
  path: "/dev/disk/by-dname/sda-part1",
  size_human: "100 GB",
  size: 100000000000,
  tags: () => [],
  type: "partition",
  used_for: "fat32 formatted filesystem mounted at /boot/efi",
});

export const networkLink = extend<Model, NetworkLink>(model, {
  mode: NetworkLinkMode.AUTO,
  subnet_id: random,
});

export const networkDiscoveredIP = define<DiscoveredIP>({
  ip_address: "1.2.3.4",
  subnet_id: random,
});

export const networkInterface = extend<Model, NetworkInterface>(model, {
  children: () => [],
  discovered: () => [],
  enabled: true,
  firmware_version: "1.0.0",
  interface_speed: 10000,
  is_boot: true,
  link_connected: true,
  link_speed: 10000,
  links: () => [],
  mac_address: (i: number) => `00:00:00:00:00:${i}`,
  name: (i: number) => `eth${i}`,
  numa_node: 0,
  params: null,
  parents: () => [],
  product: "Product",
  sriov_max_vf: 0,
  tags: () => [],
  type: NetworkInterfaceTypes.PHYSICAL,
  vendor: "Vendor",
  vlan_id: 5001,
});

export const device = extend<SimpleNode, Device>(simpleNode, {
  actions,
  extra_macs,
  fabrics,
  ip_address: "192.168.1.100",
  ip_assignment: DeviceIpAssignment.DYNAMIC,
  link_speeds,
  link_type: NodeLinkType.DEVICE,
  node_type_display: NodeTypeDisplay.DEVICE,
  owner: "admin",
  parent: null,
  primary_mac: "de:ad:be:ef:ba:c1",
  spaces,
  subnets,
  zone: modelRef,
});

export const deviceInterface = extend<NetworkInterface, DeviceNetworkInterface>(
  networkInterface,
  {
    ip_address: "192.168.1.100",
    ip_assignment: DeviceIpAssignment.DYNAMIC,
  }
);

export const deviceDetails = extend<Device, DeviceDetails>(device, {
  created: () => timestamp("Thu, 15 Oct. 2020 07:25:10"),
  description: "Device description",
  interfaces: () => [deviceInterface()],
  locked: false,
  node_type: NodeType.DEVICE,
  on_network: false,
  pool: null,
  swap_size: null,
  updated: () => timestamp("Thu, 15 Oct. 2020 07:25:10"),
});

const node = extend<SimpleNode, BaseNode>(simpleNode, {
  architecture: "amd64/generic",
  description: "a test node",
  cpu_count: 1,
  cpu_speed: 0,
  cpu_test_status: testStatus,
  distro_series: "",
  interface_test_status: testStatus,
  locked: false,
  memory: 1,
  memory_test_status: testStatus,
  network_test_status: testStatus,
  osystem: "ubuntu",
  other_test_status: testStatus,
  pool: modelRef,
  status: NodeStatus.ALLOCATED,
  status_message: "",
  status_code: 10,
  storage_test_status: testStatus,
});

export const filterGroup = define<FilterGroup>({
  dynamic: false,
  errors: null,
  for_grouping: true,
  key: FilterGroupKey.Arch,
  label: "Architecture",
  loaded: false,
  loading: false,
  options: null,
  type: FilterGroupType.String,
});

export const machine = extend<SimpleNode, Machine>(simpleNode, {
  actions,
  architecture: "amd64/generic",
  description: "a test machine",
  ephemeral_deploy: false,
  cpu_count: 1,
  cpu_test_status: testStatus,
  distro_series: "",
  memory: 1,
  memory_test_status: testStatus,
  network_test_status: testStatus,
  osystem: "ubuntu",
  other_test_status: testStatus,
  parent: null,
  pool: modelRef,
  status: NodeStatus.ALLOCATED,
  status_message: "",
  status_code: 10,
  storage_test_status: testStatus,
  error_description: "",
  extra_macs,
  fabrics,
  ip_addresses,
  link_type: NodeLinkType.MACHINE,
  locked: false,
  owner: "admin",
  physical_disk_count: 1,
  pod: null,
  power_state: PowerState.ON,
  power_type: "manual",
  pxe_mac: "de:ad:be:ef:aa:b1",
  spaces,
  storage: 8,
  testing_status: 0,
  vlan: null,
  zone: modelRef,
});

export const machineNumaNode = extend<Model, NodeNumaNode>(model, {
  cores: () => [],
  hugepages_set: () => [],
  index: sequence,
  memory: 256,
});

export const machineEventType = extend<Model, EventType>(model, {
  description: "Script",
  level: "info",
  name: "SCRIPT_DID_NOT_COMPLETE",
});

export const machineEvent = extend<Model, NodeEvent>(model, {
  created: () => timestamp("Mon, 19 Oct. 2020 07:04:37"),
  description: "smartctl-validate on name-VZJoCN timed out",
  type: machineEventType,
});

export const machineInterface = networkInterface;

export const machineDevice = define<NodeDeviceRef>({
  fqdn: "device.maas",
  interfaces: () => [],
});

export const machineIpAddress = define<NodeIpAddress>({
  ip: "192.168.1.1",
  is_boot: false,
});

export const machineDetails = extend<BaseMachine, MachineDetails>(machine, {
  link_speeds,
  node_type_display: NodeTypeDisplay.MACHINE,
  numa_nodes_count: 1,
  sriov_support: false,
  storage_tags,
  subnets,
  workload_annotations: () => ({}),
  bios_boot_method: "uefi",
  bmc: 190,
  boot_disk: null,
  commissioning_start_time: () => timestamp("Thu, 15 Oct. 2020 07:25:10"),
  commissioning_status: testStatus,
  created: () => timestamp("Thu, 15 Oct. 2020 07:25:10"),
  current_commissioning_script_set: 6188,
  current_installation_script_set: 6174,
  current_testing_script_set: 6192,
  detected_storage_layout: StorageLayout.FLAT,
  devices: () => [],
  dhcp_on: false,
  disks: () => [],
  enable_hw_sync: true,
  enable_kernel_crash_dump: false,
  error_description: "",
  error: "",
  events: () => [],
  grouped_storages: () => [],
  hardware_uuid: "F5BB1CC9-45B2-46EA-B96A-7D528A902F4B",
  has_logs: false,
  hwe_kernel: "groovy (ga-20.10)",
  interface_test_status: testStatus,
  installation_status: 3,
  interfaces: () => [],
  license_key: "",
  metadata: () => ({
    cpu_model: "Intel(R) Xeon(R) CPU E5620",
    system_vendor: "QEMU",
    system_product: "Standard PC (Q35 + ICH9, 2009)",
    system_version: "pc-q35-5.1",
    mainboard_vendor: "Canonical Ltd.",
    mainboard_product: "LXD",
    mainboard_version: "pc-q35-5.1",
    mainboard_firmware_vendor: "EFI Development Kit II / OVMF",
    mainboard_firmware_date: "02/06/2015",
    mainboard_firmware_version: "0.0.0",
    chassis_vendor: "QEMU",
    chassis_type: "Other",
    chassis_version: "pc-q35-5.1",
  }),
  min_hwe_kernel: "",
  node_type: 0,
  numa_nodes: () => [],
  on_network: false,
  power_bmc_node_count: 3,
  power_parameters: () => ({
    password: "",
    power_address: "192.168.1.1:8000",
    instance_name: "test",
  }),
  show_os_info: false,
  special_filesystems: () => [],
  storage_layout_issues: () => [],
  supported_filesystems: () => [],
  cpu_speed: 1000,
  swap_size: null,
  updated: () => timestamp("Fri, 23 Oct. 2020 05:24:41"),
  is_dpu: false,
});

export const controller = extend<BaseNode, Controller>(node, {
  actions,
  description: "a test controller",
  last_image_sync: () => timestamp("Thu, 02 Jul. 2020 22:55:00"),
  link_type: NodeLinkType.CONTROLLER,
  node_type_display: NodeTypeDisplay.REGION_AND_RACK_CONTROLLER,
  node_type: 4,
  service_ids,
  vault_configured: false,
  versions: null,
});

export const controllerDetails = extend<Controller, ControllerDetails>(
  controller,
  {
    actions,
    bios_boot_method: "uefi",
    bmc: 190,
    boot_disk: null,
    commissioning_start_time: "Thu, 15 Oct. 2020 07:25:10",
    commissioning_status: testStatus,
    created: () => timestamp("Thu, 15 Oct. 2020 07:25:10"),
    current_commissioning_script_set: 6188,
    current_installation_script_set: 6174,
    current_testing_script_set: 6192,
    default_user: "admin",
    description: "a test machine",
    detected_storage_layout: StorageLayout.FLAT,
    devices: () => [],
    dhcp_on: false,
    disks: () => [],
    dynamic: false,
    ephemeral_deploy: false,
    error_description: "",
    error: "",
    events: () => [],
    grouped_storages: () => [],
    hardware_uuid: "F5BB1CC9-45B2-46EA-B96A-7D528A902F4B",
    has_logs: false,
    hwe_kernel: "groovy (ga-20.10)",
    install_kvm: false,
    install_rackd: false,
    installation_start_time: "Thu, 15 Oct. 2020 07:25:10",
    installation_status: 3,
    interfaces: () => [],
    ip_addresses,
    last_applied_storage_layout: StorageLayout.FLAT,
    license_key: "",
    metadata: () => ({
      cpu_model: "Intel(R) Xeon(R) CPU E5620",
      system_vendor: "QEMU",
      system_product: "Standard PC (Q35 + ICH9, 2009)",
      system_version: "pc-q35-5.1",
      mainboard_vendor: "Canonical Ltd.",
      mainboard_product: "LXD",
      mainboard_version: "pc-q35-5.1",
      mainboard_firmware_vendor: "EFI Development Kit II / OVMF",
      mainboard_firmware_date: "02/06/2015",
      mainboard_firmware_version: "0.0.0",
      chassis_vendor: "QEMU",
      chassis_type: "Other",
      chassis_version: "pc-q35-5.1",
    }),
    min_hwe_kernel: "",
    node_type: NodeType.RACK_CONTROLLER,
    numa_nodes: () => [],
    on_network: false,
    owner: "admin",
    physical_disk_count: 1,
    power_bmc_node_count: 3,
    power_parameters: () => ({
      password: "",
      power_address: "192.168.1.1:8000",
      instance_name: "test",
    }),
    power_state: PowerState.ON,
    power_type: "manual",
    previous_status: NodeStatus.DEPLOYING,
    pxe_mac: "de:ad:be:ef:aa:b1",
    register_vmhost: false,
    show_os_info: false,
    special_filesystems: () => [],
    storage_layout_issues: () => [],
    storage_tags,
    storage: 8,
    supported_filesystems: () => [],
    swap_size: null,
    testing_start_time: "Thu, 15 Oct. 2020 07:25:10",
    testing_status: testStatus,
    updated: () => timestamp("Fri, 23 Oct. 2020 05:24:41"),
    vault_configured: false,
    vlan: null,
    vlan_ids: () => [],
    workload_annotations: () => ({}),
    zone: modelRef,
  }
);

export const controllerVersionInfo = define<ControllerVersionInfo>({
  version: "1.2.3",
});

export const controllerVersions = define<ControllerVersions>({
  current: controllerVersionInfo,
  origin: "latest/edge",
  up_to_date: true,
  issues: () => [],
});

export const controllerVlansHA = define<ControllerVlansHA>({
  true: 1,
  false: 1,
});

export const podStoragePool = define<PodStoragePool>({
  available: 700000000000,
  id: () => `pool-id-${random()}`,
  name: () => `pool-name-${random()}`,
  path: () => `/path/to/${random()}`,
  total: 1000000000000,
  type: "lvm",
  used: 300000000000,
});

export const podResource = define<PodResource>({
  allocated_other: 2,
  allocated_tracked: 1,
  free: 3,
});

export const podMemoryResource = define<PodMemoryResource>({
  general: podResource,
  hugepages: podResource,
});

export const podNetworkInterface = extend<Model, PodNetworkInterface>(model, {
  name: "eth0",
  numa_index: 0,
  virtual_functions: podResource,
});

export const podVM = extend<Model, PodVM>(model, {
  hugepages_backed: false,
  memory: 4068,
  pinned_cores: () => [0, 2],
  system_id: "abc123",
  unpinned_cores: 1,
});

export const podNumaCores = define<PodNumaResource<number[]>>({
  allocated: () => [0, 2],
  free: () => [1, 3],
});

export const podNumaGeneralMemory = define<PodNumaResource<number>>({
  allocated: 1024,
  free: 2048,
});

export const podNumaHugepageMemory = define<PodNumaHugepageMemory>({
  allocated: 1024,
  free: 2048,
  page_size: 4068,
});

export const podNumaMemory = define<PodNumaMemory>({
  general: podNumaGeneralMemory,
  hugepages: () => [podNumaHugepageMemory()],
});

export const podNuma = define<PodNuma>({
  cores: podNumaCores,
  memory: podNumaMemory,
  node_id: sequence,
  interfaces: () => [0, 1],
  vms: () => [0, 1],
});

export const podVmCount = define<PodVmCount>({
  tracked: 2,
  other: 1,
});

export const podStoragePoolResource = define<PodStoragePoolResource>({
  allocated_other: random,
  allocated_tracked: random,
  backend: "zfs",
  id: "abc123",
  name: "pool-name",
  path: "/path",
  total: random,
});

export const podResources = define<PodResources>({
  cores: podResource,
  interfaces: () => [podNetworkInterface()],
  memory: podMemoryResource,
  numa: () => [podNuma()],
  storage: podResource,
  storage_pools: () => ({}),
  vm_count: podVmCount,
  vms: () => [podVM()],
});

export const podProject = define<PodProject>({
  description: "this is a description",
  name: "project-name",
});

export const podPowerParameters = define<PodPowerParameters>({
  power_address: "qemu+ssh://ubuntu@127.0.0.1/system",
  power_pass: "",
});

export const pod = extend<TimestampedModel, Pod>(timestampedModel, {
  architectures,
  capabilities,
  cpu_over_commit_ratio: 10,
  cpu_speed: 1000,
  default_macvlan_mode: "",
  default_storage_pool: "b85e27c9-9d53-4821-ad64-153c53767ce9",
  host: "",
  ip_address: (i: number) => `192.168.1.${i}`,
  memory_over_commit_ratio: 8,
  name: (i: number) => `pod${i}`,
  permissions,
  pool: 1,
  power_parameters: podPowerParameters,
  resources: podResources,
  storage_pools,
  tags,
  type: PodType.VIRSH,
  version: "4.0.2",
  zone: 1,
});

export const podDetails = extend<Pod, PodDetails>(pod, {
  attached_vlans: () => [],
  boot_vlans: () => [],
});
