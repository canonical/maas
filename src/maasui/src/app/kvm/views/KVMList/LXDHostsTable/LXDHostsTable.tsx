import { GenericTable } from "@canonical/maas-react-components";
import { useSelector } from "react-redux";

import { useZones } from "@/app/api/query/zones";
import type { ZoneResponse } from "@/app/apiclient";
import urls from "@/app/base/urls";
import type { Props as RAMColumnProps } from "@/app/kvm/components/RAMColumn/RAMColumn";
import type { KVMResource, KVMStoragePoolResources } from "@/app/kvm/types";
import { useLXDHostsTableColumns } from "@/app/kvm/views/KVMList/LXDHostsTable/useLXDHostsTable/useLXDHostsTableColumns";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import vmclusterSelectors from "@/app/store/vmcluster/selectors";
import type { VMCluster } from "@/app/store/vmcluster/types";

import "./_index.scss";

export enum LxdKVMHostType {
  Cluster = "cluster",
  Single = "single",
}

export type LXDKVMHost = {
  id: number;
  cpuCores: KVMResource;
  cpuOverCommit?: number;
  cpuAllocated: number;
  defaultPoolId?: Pod["default_storage_pool"];
  hostType: LxdKVMHostType;
  hostsCount?: number;
  memory: RAMColumnProps["memory"];
  memoryOverCommit?: number;
  name: string;
  pool?: number | null;
  project?: string;
  ramAllocated: number;
  storage: KVMResource;
  storagePools: KVMStoragePoolResources;
  storageAllocated: number;
  tags?: string[];
  url: string;
  version?: string;
  vms: number;
  zone?: number | null;
  zoneName?: string;
};

export const generateSingleHostRows = (
  pods: Pod[],
  zones?: ZoneResponse[]
): LXDKVMHost[] =>
  pods.map((pod): LXDKVMHost => {
    const zone = zones?.find((zone) => pod.zone === zone.id);
    return {
      id: pod.id,
      cpuCores: pod.resources.cores,
      cpuOverCommit: pod.cpu_over_commit_ratio,
      cpuAllocated: pod.resources.cores.allocated_tracked,
      defaultPoolId: pod.default_storage_pool,
      hostType: LxdKVMHostType.Single,
      memory: pod.resources.memory,
      memoryOverCommit: pod.memory_over_commit_ratio,
      name: pod.name,
      pool: pod.pool,
      project: pod.power_parameters?.project,
      ramAllocated:
        pod.resources.memory.general.allocated_tracked +
        pod.resources.memory.hugepages.allocated_tracked,
      storage: pod.resources.storage,
      storagePools: pod.resources.storage_pools,
      storageAllocated: pod.resources.storage.allocated_tracked,
      tags: pod.tags,
      url: urls.kvm.lxd.single.index({ id: pod.id }),
      version: pod.version,
      vms: pod.resources.vm_count.tracked,
      zone: pod.zone,
      zoneName: zone?.name,
    };
  });

export const generateClusterRows = (vmclusters: VMCluster[]): LXDKVMHost[] =>
  vmclusters.map(
    (vmcluster): LXDKVMHost => ({
      id: vmcluster.id,
      cpuCores: vmcluster.total_resources.cpu,
      cpuAllocated: vmcluster.total_resources.cpu.allocated_tracked,
      hostType: LxdKVMHostType.Cluster,
      hostsCount: vmcluster.hosts.length,
      memory: vmcluster.total_resources.memory,
      name: vmcluster.name,
      pool:
        vmcluster.resource_pool || vmcluster.resource_pool === 0
          ? vmcluster.resource_pool
          : null,
      project: vmcluster.project,
      ramAllocated:
        vmcluster.total_resources.memory.general.allocated_tracked +
        vmcluster.total_resources.memory.hugepages.allocated_tracked,
      storage: vmcluster.total_resources.storage,
      storagePools: vmcluster.total_resources.storage_pools,
      storageAllocated: vmcluster.total_resources.storage.allocated_tracked,
      url: urls.kvm.lxd.cluster.index({ clusterId: vmcluster.id }),
      version: vmcluster.version,
      vms: vmcluster.virtual_machines.length,
      zone:
        vmcluster.availability_zone || vmcluster.availability_zone === 0
          ? vmcluster.availability_zone
          : null,
    })
  );

const LXDHostsTable = (): React.ReactElement | null => {
  const singleHosts = useSelector(podSelectors.lxdSingleHosts);
  const singleHostsLoading = useSelector(podSelectors.loading);
  const singleHostsLoaded = useSelector(podSelectors.loaded);
  const vmclusters = useSelector(vmclusterSelectors.all);
  const vmclustersLoading = useSelector(vmclusterSelectors.loading);
  const vmclustersLoaded = useSelector(vmclusterSelectors.loaded);

  const zones = useZones();

  const columns = useLXDHostsTableColumns();

  const rows = !(
    singleHostsLoaded &&
    !singleHosts.length &&
    vmclustersLoaded &&
    !vmclusters.length
  )
    ? generateSingleHostRows(singleHosts, zones.data?.items).concat(
        generateClusterRows(vmclusters)
      )
    : [];

  return (
    <GenericTable
      className="lxd-table"
      columns={columns}
      data={rows}
      isLoading={singleHostsLoading || vmclustersLoading}
      noData="No hosts available."
    />
  );
};

export default LXDHostsTable;
