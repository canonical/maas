import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import FabricLink from "@/app/base/components/FabricLink";
import SpaceLink from "@/app/base/components/SpaceLink";
import TableActions from "@/app/base/components/TableActions";
import VLANLink from "@/app/base/components/VLANLink";
import { useSidePanel } from "@/app/base/side-panel-context";
import { DeleteVLAN, EditVLAN } from "@/app/networks/views/VLANs/components";
import type { VLAN } from "@/app/store/vlan/types";

export type VLANsColumnDef = ColumnDef<VLAN, Partial<VLAN>>;

const useVlansTableColumns = (): VLANsColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  return useMemo(
    (): VLANsColumnDef[] => [
      {
        id: "vid",
        accessorKey: "vid",
        enableSorting: true,
        header: "VID",
        cell: ({
          row: {
            original: { id },
          },
        }) => <VLANLink id={id} />,
      },
      {
        id: "fabric",
        accessorKey: "fabric",
        enableSorting: true,
        cell: ({
          row: {
            original: { fabric },
          },
        }) => <FabricLink id={fabric} />,
      },
      {
        id: "space",
        accessorKey: "space",
        enableSorting: false,
        header: "Space",
        cell: ({ row }) => <SpaceLink id={row.original.space} />,
      },
      {
        id: "dhcp",
        accessorKey: "dhcp_on",
        enableSorting: false,
        header: "DHCP",
        cell: ({ row: { original: vlan } }) => (
          <>
            {vlan.dhcp_on
              ? "MAAS-provided"
              : vlan.external_dhcp
                ? `External (${vlan.external_dhcp})`
                : vlan.relay_vlan
                  ? "Relayed"
                  : "Disabled"}
          </>
        ),
      },
      {
        id: "actions",
        accessorKey: "id",
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
                component: DeleteVLAN,
                title: "Delete VLAN",
                props: { id },
              });
            }}
            onEdit={() => {
              openSidePanel({
                component: EditVLAN,
                title: "Edit VLAN",
                props: { id },
              });
            }}
          />
        ),
      },
    ],
    [openSidePanel]
  );
};

export default useVlansTableColumns;
