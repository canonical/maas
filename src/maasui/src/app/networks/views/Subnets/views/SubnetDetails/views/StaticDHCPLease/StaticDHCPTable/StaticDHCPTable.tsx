import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";

import useStaticDHCPTableColumns from "./useStaticDHCPTableColumns/useStaticDHCPTableColumns";

import type { ReservedIp } from "@/app/store/reservedip/types/base";

type Props = {
  subnetId: number;
  reservedIps: ReservedIp[];
  loading: boolean;
};

const StaticDHCPTable = ({
  subnetId,
  reservedIps,
  loading,
}: Props): ReactElement => {
  const columns = useStaticDHCPTableColumns({ subnetId });
  const data = reservedIps.map((reservedIp) => ({
    id: reservedIp.id,
    ipAddress: reservedIp.ip,
    macAddress: reservedIp.mac_address,
    nodeSummary: reservedIp.node_summary,
    comment: reservedIp.comment,
    nodeType: reservedIp.node_summary?.node_type,
    via: reservedIp.node_summary?.via,
  }));
  return (
    <GenericTable
      aria-label="Static DHCP leases"
      className="static-dhcp-table u-sv3"
      columns={columns}
      data={data}
      isLoading={loading}
      noData="No static DHCP leases available."
      role="table"
    />
  );
};

export default StaticDHCPTable;
