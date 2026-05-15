import { useMemo } from "react";

import { Icon } from "@canonical/react-components";
import type { ColumnDef } from "@tanstack/react-table";

import SubnetLink from "@/app/base/components/SubnetLink";

export type VLANSubnetTableData = {
  id: number;
  cidr: string;
  usage: number;
  usage_string: string;
  managed: boolean;
  allow_proxy: boolean;
  allow_dns: boolean;
};

export type VLANSubnetColumnDef = ColumnDef<
  VLANSubnetTableData,
  Partial<VLANSubnetTableData>
>;

const useVLANSubnetsTableColumns = (): VLANSubnetColumnDef[] => {
  return useMemo(
    (): VLANSubnetColumnDef[] => [
      {
        accessorKey: "cidr",
        header: "Subnet",
        cell: ({
          row: {
            original: { id },
          },
        }) => <SubnetLink id={id} />,
      },
      {
        accessorKey: "usage",
        header: "Usage",
        cell: ({
          row: {
            original: { usage_string },
          },
        }) => usage_string,
      },
      {
        accessorKey: "managed",
        header: "Managed allocation",
        cell: ({
          row: {
            original: { managed },
          },
        }) => (
          <Icon name={managed ? "tick" : "close"}>
            {managed ? "Yes" : "No"}
          </Icon>
        ),
      },
      {
        accessorKey: "allow_proxy",
        header: "Proxy access",
        cell: ({
          row: {
            original: { allow_proxy },
          },
        }) => (
          <Icon name={allow_proxy ? "tick" : "close"}>
            {allow_proxy ? "Yes" : "No"}
          </Icon>
        ),
      },
      {
        accessorKey: "allow_dns",
        header: "Allows DNS resolution",
        cell: ({
          row: {
            original: { allow_dns },
          },
        }) => (
          <Icon name={allow_dns ? "tick" : "close"}>
            {allow_dns ? "Yes" : "No"}
          </Icon>
        ),
      },
    ],
    []
  );
};

export default useVLANSubnetsTableColumns;
