import type { VMClusterMeta } from "./enum";

import type { ResourcePoolResponse, ZoneResponse } from "@/app/apiclient";
import type { APIError } from "@/app/base/types";
import type { Machine } from "@/app/store/machine/types";
import type { Pod, PodPowerParameters } from "@/app/store/pod/types";
import type { Model } from "@/app/store/types/model";
import type { GenericState } from "@/app/store/types/state";

export type VMClusterResource = {
  allocated_other: number;
  allocated_tracked: number;
  free: number;
  total: number;
};

export type VMClusterResourcesMemory = {
  hugepages: VMClusterResource;
  general: VMClusterResource;
};

export type VMClusterStoragePoolResource = {
  allocated_other: number;
  allocated_tracked: number;
  backend: string;
  free: number;
  path: string;
  total: number;
};

export type VMClusterStoragePoolResources = Record<
  string,
  VMClusterStoragePoolResource
>;

export type VMClusterResources = {
  cpu: VMClusterResource;
  memory: VMClusterResourcesMemory;
  storage: VMClusterResource;
  storage_pools: VMClusterStoragePoolResources;
  vm_count: number;
};

export type VMHost = Model & {
  availability_zone: ZoneResponse["name"];
  name: Pod["name"];
  project: PodPowerParameters["project"];
  resource_pool: ResourcePoolResponse["name"];
  tags: Pod["tags"];
};

export type VirtualMachine = {
  hugepages_backed: boolean;
  name: string;
  pinned_cores: number[];
  project: string;
  system_id: Machine["system_id"];
  unpinned_cores: number;
};

export type VMCluster = Model & {
  availability_zone: ZoneResponse["id"];
  created_at: string;
  hosts: VMHost[];
  name: string;
  project: string;
  resource_pool: ResourcePoolResponse["id"];
  total_resources: VMClusterResources;
  updated_at: string;
  version: string;
  virtual_machines: VirtualMachine[];
};

export type VMClusterEventError = {
  error: APIError;
  event: string;
};

export type VMClusterStatuses = {
  deleting: boolean;
  getting: boolean;
};

export type VMClusterState = GenericState<VMCluster, APIError> & {
  eventErrors: VMClusterEventError[];
  physicalClusters: VMCluster[VMClusterMeta.PK][][];
  statuses: VMClusterStatuses;
};
