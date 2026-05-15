import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { Col, Row, Strip } from "@canonical/react-components";
import { useSelector } from "react-redux";

import { usePools } from "@/app/api/query/pools";
import type { ResourcePoolStatisticsResponse } from "@/app/apiclient";
import { useLXDClusterHostsTableColumns } from "@/app/kvm/views/LXDClusterDetails/LXDClusterHosts/LXDClusterHostsTable/useLXDClusterHostsTableColumns/useLXDClusterHostsTableColumns";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import type { VMCluster } from "@/app/store/vmcluster/types";

import "./_index.scss";

type Props = {
  currentPage: number;
  clusterId: VMCluster["id"];
  hosts: Pod[];
  searchFilter: string;
};

export type LXDClusterHost = Pod & {
  poolName?: string;
  vms: number;
  cpuAllocated: number;
  ramAllocated: number;
  storageAllocated: number;
};

export const generateRows = (
  hosts: Pod[],
  pools: ResourcePoolStatisticsResponse[] | undefined
): LXDClusterHost[] =>
  hosts.map((host) => {
    const pool = pools?.find((pool) => host.pool === pool.id);
    return {
      ...host,
      poolName: pool?.name,
      vms: host.resources.vm_count.tracked,
      cpuAllocated: host.resources.cores.allocated_tracked,
      ramAllocated:
        host.resources.memory.general.allocated_tracked +
        host.resources.memory.hugepages.allocated_tracked,
      storageAllocated: host.resources.storage.allocated_tracked,
    };
  });

const LXDClusterHostsTable = ({
  currentPage,
  clusterId,
  hosts,
  searchFilter,
}: Props): ReactElement => {
  const pools = usePools();
  const podsLoaded = useSelector(podSelectors.loaded);
  const loaded = !pools.isPending && podsLoaded;

  const columns = useLXDClusterHostsTableColumns({ clusterId });

  // Paginate the hosts
  const VMS_PER_PAGE = 10; // Default pagination size
  const enrichedHosts = generateRows(hosts, pools.data?.items);
  const paginatedHosts = enrichedHosts.slice(
    (currentPage - 1) * VMS_PER_PAGE,
    currentPage * VMS_PER_PAGE
  );

  return (
    <>
      <Row>
        <Col size={12}>
          <GenericTable
            className="lxd-cluster-table"
            columns={columns}
            data={paginatedHosts}
            isLoading={!loaded}
            sorting={[{ id: "name", desc: true }]}
            variant="regular"
          />
        </Col>
      </Row>
      {searchFilter && paginatedHosts.length === 0 ? (
        <Strip rowClassName="u-align--center" shallow>
          <span data-testid="no-hosts">
            No hosts in this cluster match the search criteria.
          </span>
        </Strip>
      ) : null}
    </>
  );
};

export default LXDClusterHostsTable;
