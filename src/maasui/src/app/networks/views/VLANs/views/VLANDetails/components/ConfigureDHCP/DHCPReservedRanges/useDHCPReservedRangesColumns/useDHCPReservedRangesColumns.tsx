import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import FormikField from "@/app/base/components/FormikField";
import SubnetLink from "@/app/base/components/SubnetLink";
import SubnetSelect from "@/app/base/components/SubnetSelect";
import type { IPRange } from "@/app/store/iprange/types";
import type { Subnet } from "@/app/store/subnet/types";
import type { VLAN, VLANMeta } from "@/app/store/vlan/types";

export type DHCPReservedRangeData = {
  id: IPRange["id"];
  subnet: IPRange["subnet"];
  startIp: IPRange["start_ip"];
  endIp: IPRange["end_ip"];
  gatewayIp: Subnet["gateway_ip"] | "—";
  comment: string;
};

type DHCPReservedRangesColumnDef = ColumnDef<
  DHCPReservedRangeData,
  Partial<DHCPReservedRangeData>
>;

type UseDHCPReservedRangesColumnsProps = {
  hasIPRanges: boolean;
  subnetSelected: boolean;
  vlanId: VLAN[VLANMeta.PK];
};

const useDHCPReservedRangesColumns = ({
  hasIPRanges,
  subnetSelected = false,
  vlanId,
}: UseDHCPReservedRangesColumnsProps): DHCPReservedRangesColumnDef[] => {
  return useMemo(
    () => [
      {
        id: "subnet",
        accessorKey: "subnet",
        enableSorting: hasIPRanges,
        header: "Subnet",
        cell: ({ row }: { row: { original: DHCPReservedRangeData } }) =>
          hasIPRanges ? (
            <SubnetLink id={row.original.subnet} />
          ) : (
            <SubnetSelect
              labelClassName="u-visually-hidden"
              name="subnet"
              vlan={vlanId}
            />
          ),
      },
      {
        id: "startIp",
        accessorKey: "startIp",
        enableSorting: hasIPRanges,
        header: "Start IP address",
        cell: ({ row }: { row: { original: DHCPReservedRangeData } }) =>
          hasIPRanges ? (
            row.original.startIp
          ) : subnetSelected ? (
            <FormikField
              label="Start IP address"
              labelClassName="u-visually-hidden"
              name="startIP"
              type="text"
            />
          ) : null,
      },
      {
        id: "endIp",
        accessorKey: "endIp",
        enableSorting: hasIPRanges,
        header: "End IP address",
        cell: ({ row }: { row: { original: DHCPReservedRangeData } }) =>
          hasIPRanges ? (
            row.original.endIp
          ) : subnetSelected ? (
            <FormikField
              label="End IP address"
              labelClassName="u-visually-hidden"
              name="endIP"
              type="text"
            />
          ) : null,
      },
      {
        id: "gatewayIp",
        accessorKey: "gatewayIp",
        enableSorting: hasIPRanges,
        header: "Gateway IP",
        cell: ({ row }: { row: { original: DHCPReservedRangeData } }) =>
          hasIPRanges ? (
            row.original.gatewayIp
          ) : subnetSelected ? (
            <FormikField
              label="Gateway IP"
              labelClassName="u-visually-hidden"
              name="gatewayIP"
              type="text"
            />
          ) : null,
      },
      ...(hasIPRanges
        ? [
            {
              id: "comment",
              accessorKey: "comment",
              enableSorting: hasIPRanges,
              header: "Comment",
              cell: ({ row }: { row: { original: DHCPReservedRangeData } }) =>
                hasIPRanges ? row.original.comment : null,
            },
          ]
        : []),
    ],
    [hasIPRanges, subnetSelected, vlanId]
  );
};

export default useDHCPReservedRangesColumns;
