import { useMemo } from "react";

import type { ColumnDef, Row } from "@tanstack/react-table";

import type { SubnetUsedIP } from "../SubnetUsedIPs";

import NodeLink from "@/app/base/components/node/NodeLink";

export type SubnetUsedIPColumnDef = ColumnDef<
  SubnetUsedIP,
  Partial<SubnetUsedIP>
>;

const useSubnetUsedIPsColumns = (): SubnetUsedIPColumnDef[] => {
  return useMemo(
    () => [
      {
        id: "ip",
        accessorKey: "ip",
        enableSorting: true,
        header: "IP Address",
      },
      {
        id: "type",
        accessorKey: "type",
        enableSorting: true,
        header: "Type",
      },
      {
        id: "nodeHostName",
        accessorKey: "nodeHostName",
        enableSorting: true,
        header: "Node",
        cell: ({
          row: {
            original: { nodeSystemId, nodeType },
          },
        }: {
          row: Row<SubnetUsedIP>;
        }) =>
          nodeSystemId ? (
            <NodeLink nodeType={nodeType!} systemId={nodeSystemId} />
          ) : (
            "—"
          ),
      },
      {
        id: "interface",
        accessorKey: "interface",
        enableSorting: true,
        header: "Interface",
        cell: ({ row: { original } }: { row: Row<SubnetUsedIP> }) =>
          original.interface || "—",
      },
      {
        id: "usage",
        accessorKey: "usage",
        enableSorting: true,
        header: "Usage",
      },
      {
        id: "owner",
        accessorKey: "owner",
        enableSorting: true,
        header: "Owner",
        cell: ({
          row: {
            original: { owner },
          },
        }: {
          row: Row<SubnetUsedIP>;
        }) => owner || "—",
      },
      {
        id: "lastSeen",
        accessorKey: "lastSeen",
        enableSorting: false,
        header: "Last Seen",
      },
    ],
    []
  );
};

export default useSubnetUsedIPsColumns;
