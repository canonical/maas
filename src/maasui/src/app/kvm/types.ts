import type {
  PodResource,
  PodStoragePoolResource,
  PodStoragePoolResources,
} from "@/app/store/pod/types";
import type {
  VMClusterResource,
  VMClusterStoragePoolResource,
  VMClusterStoragePoolResources,
} from "@/app/store/vmcluster/types";

export type KVMResource = PodResource | VMClusterResource;

export type KVMStoragePoolResources =
  | PodStoragePoolResources
  | VMClusterStoragePoolResources;

export type KVMStoragePoolResource =
  | PodStoragePoolResource
  | VMClusterStoragePoolResource;
