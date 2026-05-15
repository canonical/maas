import { define, random } from "cooky-cutter";
import { Action } from "history";
import type { RouterState } from "redux-first-history";

import { bondOptions } from "./general";

import { ACTION_STATUS } from "@/app/base/constants";
import type { APIError, ActionState } from "@/app/base/types";
import type { ConfigState } from "@/app/store/config/types";
import { DEFAULT_STATUSES as DEFAULT_CONTROLLER_STATUSES } from "@/app/store/controller/slice";
import type {
  Controller,
  ControllerMeta,
  ControllerState,
  ControllerStatus,
  ControllerStatuses,
} from "@/app/store/controller/types";
import type { ImageSyncStatuses } from "@/app/store/controller/types/base";
import { ImageSyncStatus } from "@/app/store/controller/types/enum";
import { DEFAULT_STATUSES as DEFAULT_DEVICE_STATUSES } from "@/app/store/device/slice";
import type {
  Device,
  DeviceMeta,
  DeviceState,
  DeviceStatus,
  DeviceStatuses,
} from "@/app/store/device/types";
import type { DHCPSnippetState } from "@/app/store/dhcpsnippet/types";
import type { DomainState } from "@/app/store/domain/types";
import type { EventState } from "@/app/store/event/types";
import type { FabricState } from "@/app/store/fabric/types";
import type {
  ArchitecturesState,
  BondOptionsState,
  ComponentsToDisableState,
  DefaultMinHweKernelState,
  GeneralState,
  GeneratedCertificateState,
  HWEKernelsState,
  InstallTypeState,
  KnownArchitecturesState,
  KnownBootArchitecturesState,
  MAASURLState,
  MachineActionsState,
  OSInfoState,
  PocketsToDisableState,
  PowerTypesState,
  TLSCertificateState,
  VaultEnabledState,
  VersionState,
} from "@/app/store/general/types";
import type { IPRangeState } from "@/app/store/iprange/types";
import type { LicenseKeysState } from "@/app/store/licensekeys/types";
import { DEFAULT_STATUSES as DEFAULT_MACHINE_STATUSES } from "@/app/store/machine";
import type {
  FilterGroup,
  Machine,
  MachineEventErrors,
  MachineMeta,
  MachineState,
  MachineStateCount,
  MachineStateCounts,
  MachineStateDetails,
  MachineStateDetailsItem,
  MachineStateList,
  MachineStateListGroup,
  MachineStateLists,
  MachineStatus,
  MachineStatuses,
} from "@/app/store/machine/types";
import { FilterGroupKey, FilterGroupType } from "@/app/store/machine/types";
import type { MessageState } from "@/app/store/message/types";
import type { MsmState, MsmStatus } from "@/app/store/msm/types/base";
import type { NodeDeviceState } from "@/app/store/nodedevice/types";
import type { NodeScriptResultState } from "@/app/store/nodescriptresult/types";
import type { NotificationState } from "@/app/store/notification/types";
import type { PackageRepositoryState } from "@/app/store/packagerepository/types";
import { DEFAULT_STATUSES as DEFAULT_POD_STATUSES } from "@/app/store/pod/slice";
import type { PodState, PodStatus, PodStatuses } from "@/app/store/pod/types";
import type { ReservedIpState } from "@/app/store/reservedip/types";
import type { RootState } from "@/app/store/root/types";
import type { ScriptState } from "@/app/store/script/types";
import type { ScriptResultState } from "@/app/store/scriptresult/types";
import type { ServiceState } from "@/app/store/service/types";
import type { SpaceState } from "@/app/store/space/types";
import type { StaticRouteState } from "@/app/store/staticroute/types";
import type { StatusState } from "@/app/store/status/types";
import { DEFAULT_STATUSES as DEFAULT_SUBNET_STATUSES } from "@/app/store/subnet/slice";
import type {
  Subnet,
  SubnetMeta,
  SubnetState,
  SubnetStatus,
  SubnetStatuses,
} from "@/app/store/subnet/types";
import type { TagState } from "@/app/store/tag/types";
import type { TagStateList } from "@/app/store/tag/types/base";
import type { TokenState } from "@/app/store/token/types";
import type { EventError } from "@/app/store/types/state";
import { DEFAULT_STATUSES as DEFAULT_VLAN_STATUSES } from "@/app/store/vlan/slice";
import type {
  VLAN,
  VLANMeta,
  VLANState,
  VLANStatus,
  VLANStatuses,
} from "@/app/store/vlan/types";
import type { VMClusterState } from "@/app/store/vmcluster/types";
import type { VMClusterStatuses } from "@/app/store/vmcluster/types/base";

const defaultState = {
  errors: () => ({}),
  items: () => [],
  loaded: false,
  loading: false,
  saved: false,
  saving: false,
};

const defaultGeneralState = {
  errors: null,
  data: () => [],
  loaded: false,
  loading: false,
};

export const configState = define<ConfigState>({
  ...defaultState,
  errors: null,
});

export const controllerStatus = define<ControllerStatus>(
  DEFAULT_CONTROLLER_STATUSES
);

export const controllerStatuses = define<ControllerStatuses>({
  testNode: controllerStatus,
});

export const controllerImageSyncStatuses = define<ImageSyncStatuses>({
  testNode: ImageSyncStatus.Synced,
});

export const controllerEventError = define<
  EventError<Controller, APIError, ControllerMeta.PK>
>({
  id: random().toString(),
  error: "Uh oh",
  event: "tag",
});

export const controllerState = define<ControllerState>({
  ...defaultState,
  active: null,
  errors: null,
  eventErrors: () => [],
  imageSyncStatuses: () => ({}),
  selected: () => [],
  statuses: () => ({}),
});

export const deviceStatus = define<DeviceStatus>(DEFAULT_DEVICE_STATUSES);

export const deviceStatuses = define<DeviceStatuses>({
  testNode: deviceStatus,
});

export const deviceEventError = define<
  EventError<Device, APIError, DeviceMeta.PK>
>({
  id: random().toString(),
  error: "Uh oh",
  event: "tag",
});

export const deviceState = define<DeviceState>({
  ...defaultState,
  active: null,
  errors: null,
  eventErrors: () => [],
  selected: () => [],
  statuses: () => ({}),
});

export const dhcpSnippetState = define<DHCPSnippetState>({
  ...defaultState,
  errors: null,
});

export const eventState = define<EventState>({
  ...defaultState,
  errors: null,
});

export const fabricState = define<FabricState>({
  ...defaultState,
  active: null,
  errors: null,
});

export const ipRangeState = define<IPRangeState>({
  ...defaultState,
  errors: null,
});

export const licenseKeysState = define<LicenseKeysState>({
  ...defaultState,
});

export const machineStateListGroup = define<MachineStateListGroup>({
  collapsed: false,
  count: 15,
  items: () => [],
  name: null,
  value: null,
});

export const fetchedAt = define<number>(Date.now());

export const maasURLState = define<MAASURLState>({
  ...defaultGeneralState,
  data: "http://example.com/maas",
});

export const machineStateList = define<MachineStateList>({
  count: null,
  cur_page: null,
  errors: null,
  groups: null,
  loaded: false,
  loading: false,
  stale: false,
  num_pages: null,
  params: null,
  fetchedAt: () => fetchedAt(),
  refetchedAt: null,
  refetching: false,
});

export const machineActionState = define<ActionState>({
  status: ACTION_STATUS.idle,
  errors: null,
  successCount: 0,
});

export const machineStateLists = define<MachineStateLists>({
  testNode: machineStateList,
});

export const machineStatus = define<MachineStatus>(DEFAULT_MACHINE_STATUSES);

export const machineStatuses = define<MachineStatuses>({
  testNode: machineStatus,
});

export const machineStateCount = define<MachineStateCount>({
  count: null,
  errors: null,
  loaded: false,
  loading: false,
  stale: false,
  params: null,
  fetchedAt,
  refetchedAt: null,
  refetching: false,
});

export const machineFilterGroup = define<FilterGroup>({
  dynamic: false,
  errors: null,
  for_grouping: false,
  key: FilterGroupKey.AgentName,
  label: "filter group",
  loaded: false,
  loading: false,
  options: () => [],
  type: FilterGroupType.String,
});

export const machineStateCounts = define<MachineStateCounts>({
  testId: machineStateCount,
});

export const machineStateDetailsItem = define<MachineStateDetailsItem>({
  errors: null,
  loaded: false,
  loading: false,
  system_id: () => random().toString(),
});

export const machineStateDetails = define<MachineStateDetails>({
  testNode: machineStateDetailsItem,
});

export const machineEventError = define<
  EventError<Machine, APIError<MachineEventErrors>, MachineMeta.PK>
>({
  id: random().toString(),
  error: "Uh oh",
  event: "tag",
});

export const machineState = define<MachineState>({
  ...defaultState,
  actions: () => ({}),
  active: null,
  counts: () => ({}),
  details: () => ({}),
  eventErrors: () => [],
  filters: () => [],
  filtersLoaded: false,
  filtersLoading: false,
  lists: () => ({}),
  selected: null,
  statuses: () => ({}),
});

export const scriptState = define<ScriptState>({
  ...defaultState,
});

export const spaceState = define<SpaceState>({
  ...defaultState,
  active: null,
  errors: null,
});

export const staticRouteState = define<StaticRouteState>({
  ...defaultState,
  errors: null,
});

export const tokenState = define<TokenState>({
  ...defaultState,
  errors: null,
});

export const packageRepositoryState = define<PackageRepositoryState>({
  ...defaultState,
  errors: null,
});

export const podStatus = define<PodStatus>(DEFAULT_POD_STATUSES);

export const podStatuses = define<PodStatuses>({
  1: podStatus,
});

export const podState = define<PodState>({
  ...defaultState,
  active: null,
  errors: null,
  projects: () => ({}),
  statuses: () => ({}),
});

export const notificationState = define<NotificationState>({
  ...defaultState,
  errors: null,
});

export const messageState = define<MessageState>({
  items: () => [],
});

export const msmStatus = define<MsmStatus | null>({
  running: "not_connected",
  smUrl: "http://example.com",
  startTime: "2021-01-01",
});
export const msmState = define<MsmState>({
  status: msmStatus,
  loading: false,
  loaded: false,
  errors: null,
});

export const architecturesState = define<ArchitecturesState>({
  ...defaultGeneralState,
});

export const bondOptionsState = define<BondOptionsState>({
  ...defaultGeneralState,
  data: () => bondOptions(),
});

export const componentsToDisableState = define<ComponentsToDisableState>({
  ...defaultGeneralState,
});

export const defaultMinHweKernelState = define<DefaultMinHweKernelState>({
  ...defaultGeneralState,
  data: "",
});

export const installTypeState = define<InstallTypeState>({
  ...defaultGeneralState,
});

export const generatedCertificateState = define<GeneratedCertificateState>({
  ...defaultGeneralState,
  data: null,
});

export const hweKernelsState = define<HWEKernelsState>({
  ...defaultGeneralState,
});

export const knownArchitecturesState = define<KnownArchitecturesState>({
  ...defaultGeneralState,
});

export const knownBootArchitecturesState = define<KnownBootArchitecturesState>({
  ...defaultGeneralState,
});

export const machineActionsState = define<MachineActionsState>({
  ...defaultGeneralState,
  data: () => [],
});

export const osInfoState = define<OSInfoState>({
  ...defaultGeneralState,
  data: null,
});

export const pocketsToDisableState = define<PocketsToDisableState>({
  ...defaultGeneralState,
});

export const powerTypesState = define<PowerTypesState>({
  ...defaultGeneralState,
});

export const tlsCertificateState = define<TLSCertificateState>({
  ...defaultGeneralState,
  data: null,
});

export const vaultEnabledState = define<VaultEnabledState>({
  ...defaultGeneralState,
  data: false,
});

export const versionState = define<VersionState>({
  ...defaultGeneralState,
  data: "",
});

export const generalState = define<GeneralState>({
  architectures: architecturesState,
  bondOptions: bondOptionsState,
  componentsToDisable: componentsToDisableState,
  defaultMinHweKernel: defaultMinHweKernelState,
  generatedCertificate: generatedCertificateState,
  hweKernels: hweKernelsState,
  installType: installTypeState,
  knownArchitectures: knownArchitecturesState,
  knownBootArchitectures: knownBootArchitecturesState,
  maasURL: maasURLState,
  machineActions: machineActionsState,
  osInfo: osInfoState,
  pocketsToDisable: pocketsToDisableState,
  powerTypes: powerTypesState,
  tlsCertificate: tlsCertificateState,
  vaultEnabled: vaultEnabledState,
  version: versionState,
});

export const statusState = define<StatusState>({
  authenticated: false,
  authenticating: false,
  authenticationError: null,
  connected: false,
  connecting: false,
  connectedCount: 0,
  error: null,
  externalAuthURL: "http://example.com/auth",
  externalLoginURL: "http://example.com/login",
  noUsers: false,
});

export const domainState = define<DomainState>({
  ...defaultState,
  active: null,
  errors: null,
});

export const nodeDeviceState = define<NodeDeviceState>({
  ...defaultState,
});

export const nodeScriptResultState = define<NodeScriptResultState>({
  items: () => ({}),
});

export const reservedIpState = define<ReservedIpState>({
  ...defaultState,
  errors: null,
});

export const scriptResultState = define<ScriptResultState>({
  ...defaultState,
  history: () => ({}),
  logs: () => null,
});

export const serviceState = define<ServiceState>({
  ...defaultState,
  errors: null,
});

export const subnetStatus = define<SubnetStatus>(DEFAULT_SUBNET_STATUSES);

export const subnetStatuses = define<SubnetStatuses>({
  1: subnetStatus,
});

export const subnetEventError = define<
  EventError<Subnet, APIError, SubnetMeta.PK>
>({
  id: random(),
  error: "Uh oh",
  event: "scan",
});

export const subnetState = define<SubnetState>({
  ...defaultState,
  active: null,
  errors: null,
  eventErrors: () => [],
  statuses: () => ({}),
});

export const tagStateListFactory = define<TagStateList>({
  errors: null,
  items: null,
  loaded: false,
  loading: false,
});

export const tagState = define<TagState>({
  ...defaultState,
  lists: () => ({}),
  errors: null,
});

export const vlanStatus = define<VLANStatus>(DEFAULT_VLAN_STATUSES);

export const vlanStatuses = define<VLANStatuses>({
  1: vlanStatus,
});

export const vlanEventError = define<EventError<VLAN, APIError, VLANMeta.PK>>({
  id: random(),
  error: "Uh oh",
  event: "configureDHCP",
});

export const vlanState = define<VLANState>({
  ...defaultState,
  active: null,
  errors: null,
  eventErrors: () => [],
  statuses: () => ({}),
});

export const vmClusterStatuses = define<VMClusterStatuses>({
  deleting: false,
  getting: false,
});

export const vmClusterState = define<VMClusterState>({
  ...defaultState,
  eventErrors: () => [],
  physicalClusters: () => [],
  statuses: vmClusterStatuses,
});

export const locationState = define<RouterState["location"]>({
  pathname: "/",
  search: "",
  state: null,
  hash: "",
  key: "",
});

export const routerState = define<RouterState>({
  location: locationState,
  action: Action.Pop,
});

export const rootState = define<RootState>({
  config: configState,
  controller: controllerState,
  device: deviceState,
  event: eventState,
  dhcpsnippet: dhcpSnippetState,
  domain: domainState,
  fabric: fabricState,
  general: generalState,
  iprange: ipRangeState,
  licensekeys: licenseKeysState,
  machine: machineState,
  message: messageState,
  msm: msmState,
  nodedevice: nodeDeviceState,
  notification: notificationState,
  nodescriptresult: nodeScriptResultState,
  packagerepository: packageRepositoryState,
  pod: podState,
  reservedip: reservedIpState,
  router: routerState,
  scriptresult: scriptResultState,
  script: scriptState,
  service: serviceState,
  space: spaceState,
  staticroute: staticRouteState,
  status: statusState,
  subnet: subnetState,
  tag: tagState,
  token: tokenState,
  vlan: vlanState,
  vmcluster: vmClusterState,
});
