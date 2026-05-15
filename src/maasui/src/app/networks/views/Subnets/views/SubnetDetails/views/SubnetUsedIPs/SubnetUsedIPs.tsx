import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { useSelector } from "react-redux";

import useSubnetUsedIPsColumns from "./useSubnetUsedIPsColumns/useSubnetUsedIPsColumns";

import TitledSection from "@/app/base/components/TitledSection";
import usePagination from "@/app/base/hooks/usePagination/usePagination";
import type { RootState } from "@/app/store/root/types";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import {
  getIPTypeDisplay,
  getIPUsageDisplay,
  isSubnetDetails,
} from "@/app/store/subnet/utils";
import type { UtcDatetime } from "@/app/store/types/model";
import type { NodeType } from "@/app/store/types/node";

export type Props = {
  subnetId: Subnet[SubnetMeta.PK] | null;
};

export type SubnetUsedIP = {
  id: number;
  ip: string;
  type: string;
  nodeHostName?: string;
  nodeSystemId?: string;
  nodeType?: NodeType;
  interface?: string;
  usage: string;
  owner?: string;
  lastSeen: UtcDatetime;
};

const getSubnetUsedIPs = (subnet: Subnet | null): SubnetUsedIP[] => {
  if (!isSubnetDetails(subnet)) {
    return [];
  }

  return subnet.ip_addresses.map(
    (ip, index): SubnetUsedIP => ({
      id: index,
      ip: ip.ip,
      type: getIPTypeDisplay(ip.alloc_type),
      nodeHostName: ip.node_summary?.hostname,
      nodeSystemId: ip.node_summary?.system_id,
      nodeType: ip.node_summary?.node_type,
      interface: ip.node_summary?.via,
      usage: getIPUsageDisplay(ip),
      owner: ip.user,
      lastSeen: ip.updated,
    })
  );
};

const SubnetUsedIPs = ({ subnetId }: Props): ReactElement => {
  const subnet = useSelector((state: RootState) =>
    subnetSelectors.getById(state, subnetId)
  );
  const loading = useSelector(subnetSelectors.loading);

  const { page, size, handlePageSizeChange, setPage } = usePagination();
  const columns = useSubnetUsedIPsColumns();
  const data = getSubnetUsedIPs(subnet);

  return (
    <TitledSection
      className="u-no-padding--top u-no-padding--bottom"
      title="Used IP addresses"
    >
      <GenericTable
        className="used-ip-table"
        columns={columns}
        data={data.slice(size * (page - 1), size * page)}
        isLoading={loading}
        noData={"No IP addresses for this subnet."}
        pagination={{
          currentPage: page,
          dataContext: "IP addresses",
          handlePageSizeChange: handlePageSizeChange,
          isPending: loading,
          itemsPerPage: size,
          setCurrentPage: setPage,
          totalItems: data.length,
        }}
        sorting={[{ id: "ip", desc: false }]}
      />
    </TitledSection>
  );
};

export default SubnetUsedIPs;
