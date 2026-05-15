import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";
import { Link } from "react-router";

import DeleteDHCPLease from "../../DeleteDHCPLease";
import ReserveDHCPLease from "../../ReserveDHCPLease";

import TableActions from "@/app/base/components/TableActions";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { ReservedIpNodeSummary } from "@/app/store/reservedip/types/base";
import { getNodeUrl } from "@/app/store/reservedip/utils";
import type { NodeType } from "@/app/store/types/node";
import { getNodeTypeDisplay } from "@/app/store/utils";

export type StaticDHCPTableData = {
  id: number;
  macAddress: string;
  ipAddress: string;
  nodeSummary?: ReservedIpNodeSummary;
  via?: string;
  nodeType?: NodeType;
  comment?: string;
};

export type StaticDHCPColumnDef = ColumnDef<
  StaticDHCPTableData,
  Partial<StaticDHCPTableData>
>;

const useStaticDHCPTableColumns = ({
  subnetId,
}: {
  subnetId: number;
}): StaticDHCPColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  return useMemo(
    (): StaticDHCPColumnDef[] => [
      {
        accessorKey: "ipAddress",
        header: () => "IP Address",
        enableSorting: false,
      },
      {
        accessorKey: "macAddress",
        header: "MAC Address",
        enableSorting: false,
        cell: ({
          row: {
            original: { macAddress },
          },
        }) => macAddress || "—",
      },
      {
        accessorKey: "node",
        header: "Node",
        enableSorting: false,
        cell: ({
          row: {
            original: { nodeSummary },
          },
        }) =>
          nodeSummary ? (
            <Link to={getNodeUrl(nodeSummary.node_type, nodeSummary.system_id)}>
              <strong>{nodeSummary.hostname}</strong>.
              {nodeSummary.fqdn.split(".")[1]}
            </Link>
          ) : (
            "—"
          ),
      },
      {
        accessorKey: "interface",
        header: "Interface",
        enableSorting: false,
        cell: ({
          row: {
            original: { nodeSummary },
          },
        }) => nodeSummary?.via || "—",
      },
      {
        accessorKey: "usage",
        header: "Usage",
        enableSorting: false,
        cell: ({
          row: {
            original: { nodeSummary },
          },
        }) =>
          nodeSummary?.node_type !== undefined
            ? getNodeTypeDisplay(nodeSummary.node_type)
            : "—",
      },
      {
        accessorKey: "comment",
        header: "Comment",
        enableSorting: false,
        cell: ({
          row: {
            original: { comment },
          },
        }) => comment || "—",
      },
      {
        accessorKey: "actions",
        header: "Actions",
        enableSorting: false,
        cell: ({
          row: {
            original: { id },
          },
        }) => (
          <TableActions
            onDelete={() => {
              openSidePanel({
                component: DeleteDHCPLease,
                title: "Delete DHCP lease",
                props: {
                  reservedIpId: id,
                },
              });
            }}
            onEdit={() => {
              openSidePanel({
                component: ReserveDHCPLease,
                title: "Edit DHCP lease",
                props: {
                  reservedIpId: id,
                  subnetId,
                },
              });
            }}
          />
        ),
      },
    ],
    [openSidePanel, subnetId]
  );
};

export default useStaticDHCPTableColumns;
