import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import DoubleRow from "@/app/base/components/DoubleRow";
import type { NetworkInterface } from "@/app/store/types/node";

export type CloneNetworkRowData = {
  id: NetworkInterface["id"];
  name: string;
  subnet?: string;
  fabric?: string;
  vlan: string | null;
  type: string | null;
  numaNodes?: string;
  dhcp?: string;
  isParent?: boolean;
};

export type CloneNetworkColumnDef = ColumnDef<
  CloneNetworkRowData,
  Partial<CloneNetworkRowData>
>;

const useCloneNetworkTableColumns = (): CloneNetworkColumnDef[] => {
  return useMemo(
    (): CloneNetworkColumnDef[] => [
      {
        id: "name",
        accessorKey: "name",
        enableSorting: false,
        header: () => (
          <span className="name-col">
            <div>Interface</div>
            <div>Subnet</div>
          </span>
        ),
        cell: ({
          row: {
            original: { name, subnet, isParent },
          },
        }) => (
          <DoubleRow
            primary={name}
            primaryTitle={name}
            secondary={!isParent ? subnet : null}
            secondaryTitle={subnet}
          />
        ),
      },
      {
        id: "fabric",
        accessorKey: "fabric",
        enableSorting: false,
        header: () => (
          <span className="fabric-col">
            <div>Fabric</div>
            <div>VLAN</div>
          </span>
        ),
        cell: ({
          row: {
            original: { fabric, vlan },
          },
        }) => (
          <DoubleRow
            primary={fabric}
            primaryTitle={fabric}
            secondary={vlan}
            secondaryTitle={vlan}
          />
        ),
      },
      {
        id: "type",
        accessorKey: "type",
        enableSorting: false,
        header: () => (
          <span className="type-col">
            <div>Type</div>
            <div>NUMA node</div>
          </span>
        ),
        cell: ({
          row: {
            original: { type, numaNodes },
          },
        }) => (
          <DoubleRow
            primary={type}
            primaryTitle={type}
            secondary={numaNodes}
            secondaryTitle={numaNodes}
          />
        ),
      },
      {
        id: "dhcp",
        accessorKey: "dhcp",
        enableSorting: false,
        header: () => <span className="dhcp-col">DHCP</span>,
      },
    ],
    []
  );
};

export default useCloneNetworkTableColumns;
