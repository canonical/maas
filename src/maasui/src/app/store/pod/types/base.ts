import type { ValueOf } from "@canonical/react-components";

import type { PodType } from "../constants";

import type { APIError } from "@/app/base/types";
import type {
  CertificateData,
  CertificateMetadata,
} from "@/app/store/general/types";
import type { Model, TimestampedModel } from "@/app/store/types/model";
import type { Node } from "@/app/store/types/node";
import type { GenericState } from "@/app/store/types/state";
import type { VMCluster, VMClusterMeta } from "@/app/store/vmcluster/types";

export type PodActions = "compose" | "refresh" | "remove";

export type PodStoragePool = {
  available: number;
  id: string;
  name: string;
  path: string;
  total: number;
  type: string;
  used: number;
};

export type PodResource = {
  allocated_other: number;
  allocated_tracked: number;
  free: number;
};

export type PodMemoryResource = {
  hugepages: PodResource;
  general: PodResource;
};

export type PodNetworkInterface = Model & {
  name: string;
  numa_index: PodNuma["node_id"];
  virtual_functions: PodResource;
};

export type PodVM = Model & {
  hugepages_backed: boolean;
  memory: number;
  pinned_cores: number[];
  system_id: Node["system_id"];
  unpinned_cores: number;
};

export type PodNumaResource<T> = {
  allocated: T;
  free: T;
};

export type PodNumaHugepageMemory = PodNumaResource<number> & {
  page_size: number;
};

export type PodNumaMemory = {
  hugepages: PodNumaHugepageMemory[];
  general: PodNumaResource<number>;
};

export type PodNuma = {
  cores: PodNumaResource<number[]>;
  memory: PodNumaMemory;
  interfaces: PodNetworkInterface["id"][];
  node_id: number;
  vms: PodVM["id"][];
};

export type PodVmCount = {
  tracked: number;
  other: number;
};

export type PodStoragePoolResource = {
  allocated_other: number;
  allocated_tracked: number;
  backend: string;
  id: string;
  name: string;
  path: string;
  total: number;
};

export type PodStoragePoolResources = Record<string, PodStoragePoolResource>;

export type PodResources = {
  cores: PodResource;
  interfaces: PodNetworkInterface[];
  memory: PodMemoryResource;
  numa: PodNuma[];
  storage: PodResource;
  storage_pools: PodStoragePoolResources;
  vm_count: PodVmCount;
  vms: PodVM[];
};

export type PodPowerParameters = {
  certificate?: CertificateData["certificate"];
  key?: CertificateData["private_key"];
  power_address?: string;
  power_pass?: string;
  project?: string;
};

export type LxdServerGroup = {
  address: PodPowerParameters["power_address"];
  pods: Pod[];
};

// BasePod is returned from the server when using "pod.list", and is used in the
// pod list pages. This type is missing some properties due to an optimisation
// on the backend to reduce the amount of database queries on list pages.
export type BasePod = TimestampedModel & {
  architectures: string[];
  capabilities: string[];
  cluster?: VMCluster[VMClusterMeta.PK];
  cpu_over_commit_ratio: number;
  cpu_speed: number;
  default_macvlan_mode: string;
  default_storage_pool: string | null;
  host: string | null;
  ip_address: number | string;
  memory_over_commit_ratio: number;
  name: string;
  permissions: string[];
  pool: number;
  power_parameters?: PodPowerParameters;
  resources: PodResources;
  storage_pools: PodStoragePool[];
  tags: string[];
  type: ValueOf<typeof PodType>;
  version: string;
  zone: number;
};

// PodDetails is returned from the server when using "pod.get", and is used in the
// pod details pages. This type contains all possible properties of a pod model.
export type PodDetails = BasePod & {
  attached_vlans: number[];
  boot_vlans: number[];
  certificate?: CertificateMetadata;
};

// Depending on where the user has navigated in the app, pods in state can
// either be of type Pod or PodDetails.
export type Pod = BasePod | PodDetails;

export type PodStatus = {
  composing: boolean;
  deleting: boolean;
  refreshing: boolean;
};

export type PodStatuses = Record<string, PodStatus>;

export type PodProject = {
  description: string;
  name: string;
};

export type PodProjects = Record<string, PodProject[]>;

export type PodState = GenericState<Pod, APIError> & {
  active: number | null;
  projects: PodProjects;
  statuses: PodStatuses;
};
