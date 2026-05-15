import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import DhcpDelete from "../../DhcpDelete";
import DhcpEdit from "../../DhcpEdit";
import DhcpTarget from "../../DhcpTarget";

import DhcpSnippetType from "@/app/base/components/DhcpSnippetType";
import TableActions from "@/app/base/components/TableActions";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { DHCPSnippet } from "@/app/store/dhcpsnippet/types";
import { formatUtcDatetime } from "@/app/utils/time";

export type DHCPListColumnDef = ColumnDef<DHCPSnippet, Partial<DHCPSnippet>>;

const useDHCPListColumns = (): DHCPListColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  return useMemo(
    () => [
      {
        accessorKey: "name",
        header: "Snippet name",
      },
      {
        accessorKey: "type",
        header: "Type",
        cell: ({
          row: {
            original: { node, iprange, subnet },
          },
        }) => (
          <DhcpSnippetType
            ipRangeId={iprange}
            nodeId={node}
            subnetId={subnet}
          />
        ),
      },
      {
        accessorKey: "target",
        header: "Applies To",
        cell: ({
          row: {
            original: { node, subnet },
          },
        }) =>
          (node || subnet) && <DhcpTarget nodeId={node} subnetId={subnet} />,
      },
      {
        accessorKey: "description",
        header: "Description",
      },
      {
        accessorKey: "enabled",
        header: "Enabled",
        cell: ({ row: { original } }) => (original.enabled ? "Yes" : "No"),
      },
      {
        accessorKey: "updated",
        header: "Last Edited",
        cell: ({
          row: {
            original: { updated },
          },
        }) => {
          return updated ? formatUtcDatetime(updated) : "Never";
        },
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
                component: DhcpDelete,
                title: "Delete DHCP snippet",
                props: {
                  id,
                },
              });
            }}
            onEdit={() => {
              openSidePanel({
                component: DhcpEdit,
                title: "Edit DHCP snippet",
                props: {
                  id,
                },
              });
            }}
          />
        ),
      },
    ],
    [openSidePanel]
  );
};

export default useDHCPListColumns;
