import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import AddReservedRange from "../../AddReservedRange";
import DeleteReservedRange from "../../DeleteReservedRange";
import { Labels } from "../ReservedRangesTable";

import SubnetLink from "@/app/base/components/SubnetLink";
import TableActions from "@/app/base/components/TableActions";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { IPRangeType } from "@/app/store/iprange/types";

export type ReservedRangesTableData = {
  id: number | string;
  ipRangeId?: number;
  subnet: number | null;
  startIp: string;
  endIp: string;
  owner: string;
  type: string;
  comment: string;
  createType: IPRangeType;
};

export type ReservedRangesColumnsDef = ColumnDef<
  ReservedRangesTableData,
  Partial<ReservedRangesTableData>
>;

const useReservedRangesColumns = (
  showSubnetColumn: boolean
): ReservedRangesColumnsDef[] => {
  const { openSidePanel } = useSidePanel();
  return useMemo((): ReservedRangesColumnsDef[] => {
    const columns: ReservedRangesColumnsDef[] = [
      {
        accessorKey: "startIp",
        header: Labels.StartIP,
      },
      {
        accessorKey: "endIp",
        header: Labels.EndIP,
      },
      {
        accessorKey: "owner",
        header: Labels.Owner,
      },
      {
        accessorKey: "type",
        header: Labels.Type,
      },
      {
        accessorKey: "comment",
        header: Labels.Comment,
      },
      {
        accessorKey: "actions",
        header: Labels.Actions,
        enableSorting: false,
        cell: ({
          row: {
            original: { ipRangeId, createType },
          },
        }) => (
          <TableActions
            onDelete={() => {
              openSidePanel({
                component: DeleteReservedRange,
                title: "Delete reserved range",
                props: {
                  ipRangeId: ipRangeId!,
                },
              });
            }}
            onEdit={() => {
              openSidePanel({
                component: AddReservedRange,
                title: "Edit reserved range",
                props: {
                  createType,
                  ipRangeId: ipRangeId!,
                },
              });
            }}
          />
        ),
      },
    ];

    // When viewing a VLAN, include Subnet as the first column
    if (showSubnetColumn) {
      columns.unshift({
        accessorKey: "subnet",
        header: Labels.Subnet,
        cell: ({
          row: {
            original: { subnet },
          },
        }) => <SubnetLink id={subnet} />,
      });
    }
    return columns;
  }, [openSidePanel, showSubnetColumn]);
};

export default useReservedRangesColumns;
