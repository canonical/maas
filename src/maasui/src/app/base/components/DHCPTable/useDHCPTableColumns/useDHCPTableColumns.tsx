import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import DhcpSnippetType from "../../DhcpSnippetType";
import TableActions from "../../TableActions";

import { useSidePanel } from "@/app/base/side-panel-context";
import DhcpEdit from "@/app/settings/views/Dhcp/DhcpEdit";
import type { DHCPSnippet } from "@/app/store/dhcpsnippet/types";
import type { IPRange } from "@/app/store/iprange/types";
import { getIpRangeDisplayName } from "@/app/store/iprange/utils";
import type { Subnet } from "@/app/store/subnet/types";
import type { Node } from "@/app/store/types/node";
import { isId } from "@/app/utils";

export type DHCPTableColumnDef = ColumnDef<DHCPSnippet, Partial<DHCPSnippet>>;

type Props = {
  originalNode?: Node;
  subnets?: Subnet[];
  ipranges?: IPRange[];
};

const useDHCPTableColumns = ({
  originalNode,
  subnets,
  ipranges,
}: Props): DHCPTableColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  return useMemo(
    () => [
      {
        accessorKey: "name",
        header: "Name",
      },
      {
        accessorKey: "type",
        header: "Type",
        cell: ({
          row: {
            original: { node, iprange, subnet },
          },
        }) => {
          return (
            <DhcpSnippetType
              ipRangeId={iprange}
              nodeId={node}
              subnetId={subnet}
            />
          );
        },
      },
      {
        accessorKey: "applies_to",
        header: "Applies To",
        cell: ({
          row: {
            original: { node, iprange, subnet },
          },
        }) => {
          let appliesTo: string | null = null;
          if (isId(node) && originalNode) {
            appliesTo = originalNode.fqdn;
          } else if (isId(iprange) && ipranges?.length) {
            const ipRange = ipranges.find(({ id }) => id === iprange);
            appliesTo = getIpRangeDisplayName(ipRange);
          } else if (isId(subnet) && subnets?.length) {
            appliesTo = subnets.find(({ id }) => id === subnet)?.name || "";
          }
          return appliesTo ?? "";
        },
      },
      {
        accessorKey: "enabled",
        header: "Enabled",
        enableSorting: true,
        cell: ({ row: { original } }) => (original.enabled ? "Yes" : "No"),
      },
      {
        accessorKey: "description",
        header: "Description",
        enableSorting: true,
        cell: ({ row: { original } }) => original.description,
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
            onEdit={() => {
              openSidePanel({
                component: DhcpEdit,
                props: { id },
                title: "Edit DHCP Snippet",
              });
            }}
          />
        ),
      },
    ],
    [ipranges, openSidePanel, subnets, originalNode]
  );
};

export default useDHCPTableColumns;
