import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import SpaceLink from "@/app/base/components/SpaceLink";
import SubnetLink from "@/app/base/components/SubnetLink";
import VLANLink from "@/app/base/components/VLANLink";
import type { Subnet } from "@/app/store/subnet/types";
import type { VLAN } from "@/app/store/vlan/types";

export type FabricVLANsRowData = {
  id: VLAN["id"];
  vid: VLAN["vid"];
  spaceId?: VLAN["space"];
  subnetId?: Subnet["id"];
  subnetAvailableIps?: Subnet["statistics"]["available_string"];
  children?: FabricVLANsRowData[];
  isChildRow: boolean;
};

type FabricVLANsColumnDef = ColumnDef<
  FabricVLANsRowData,
  Partial<FabricVLANsRowData>
>;

const useFabricVLANsTableColumns = (): FabricVLANsColumnDef[] => {
  return useMemo(
    () => [
      {
        id: "vlan",
        accessorKey: "vid",
        enableSorting: false,
        header: "VLAN",
        cell: ({
          row: {
            original: { id, isChildRow },
          },
        }) => (isChildRow ? "" : <VLANLink id={id} />),
      },
      {
        id: "space",
        accessorKey: "spaceId",
        enableSorting: false,
        header: "Space",
        cell: ({
          row: {
            original: { spaceId, isChildRow },
          },
        }) => (isChildRow ? "" : <SpaceLink id={spaceId} />),
      },
      {
        id: "subnets",
        accessorKey: "subnetId",
        enableSorting: false,
        header: "Subnets",
        cell: ({
          row: {
            original: { subnetId },
          },
        }) => (!subnetId ? "No subnets" : <SubnetLink id={subnetId} />),
      },
      {
        id: "available",
        accessorKey: "subnetAvailableIps",
        enableSorting: false,
        header: "Available",
        cell: ({
          row: {
            original: { subnetAvailableIps },
          },
        }) => subnetAvailableIps ?? "—",
      },
    ],
    []
  );
};

export default useFabricVLANsTableColumns;
