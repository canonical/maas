import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import TableHeader from "@/app/base/components/TableHeader";
import DHCPColumn from "@/app/base/components/node/networking/DHCPColumn";
import FabricColumn from "@/app/base/components/node/networking/FabricColumn";
import NameColumn from "@/app/base/components/node/networking/NameColumn";
import IPColumn from "@/app/base/components/node/networking/NetworkTable/IPColumn";
import PXEColumn from "@/app/base/components/node/networking/NetworkTable/PXEColumn";
import SpeedColumn from "@/app/base/components/node/networking/NetworkTable/SpeedColumn";
import SubnetColumn from "@/app/base/components/node/networking/SubnetColumn";
import TypeColumn from "@/app/base/components/node/networking/TypeColumn";
import type { InterfaceTableRow } from "@/app/machines/views/MachineDetails/MachineNetwork/InterfaceFormTable/InterfaceFormTable";

export type InterfaceFormTableColumnDef = ColumnDef<
  InterfaceTableRow,
  Partial<InterfaceTableRow>
>;

const useInterfaceFormTableColumns = (): InterfaceFormTableColumnDef[] => {
  return useMemo(
    () => [
      {
        id: "name",
        enableSorting: false,
        header: () => (
          <>
            <span>Name</span>
            <br />
            <span>MAC</span>
          </>
        ),
        cell: ({ row: { original } }) => (
          <NameColumn
            link={original.link}
            nic={original.nic}
            node={original.machine}
          />
        ),
      },
      {
        id: "pxe",
        enableSorting: false,
        header: () => (
          <TableHeader className="p-double-row__header-spacer">PXE</TableHeader>
        ),
        cell: ({ row: { original } }) => (
          <PXEColumn
            link={original.link}
            nic={original.nic}
            node={original.machine}
          />
        ),
      },
      {
        id: "speed",
        enableSorting: false,
        header: () => (
          <TableHeader className="p-double-row__header-spacer">
            Link/interface speed
          </TableHeader>
        ),
        cell: ({ row: { original } }) => (
          <SpeedColumn
            link={original.link}
            nic={original.nic}
            node={original.machine}
          />
        ),
      },
      {
        id: "type",
        enableSorting: false,
        header: () => (
          <>
            <TableHeader className="p-double-row__header-spacer">
              Type
            </TableHeader>
            <TableHeader className="p-double-row__header-spacer">
              NUMA node
            </TableHeader>
          </>
        ),
        cell: ({ row: { original } }) => (
          <TypeColumn
            link={original.link}
            nic={original.nic}
            node={original.machine}
          />
        ),
      },
      {
        id: "fabric",
        enableSorting: false,
        header: () => (
          <>
            <span>Fabric</span>
            <br />
            <span>VLAN</span>
          </>
        ),
        cell: ({ row: { original } }) => (
          <FabricColumn
            link={original.link}
            nic={original.nic}
            node={original.machine}
          />
        ),
      },
      {
        id: "subnet",
        enableSorting: false,
        header: () => (
          <>
            <span>Subnet</span>
            <br />
            <span>Name</span>
          </>
        ),
        cell: ({ row: { original } }) => (
          <SubnetColumn
            link={original.link}
            nic={original.nic}
            node={original.machine}
          />
        ),
      },
      {
        id: "ip",
        enableSorting: false,
        header: () => (
          <>
            <span>IP Address</span>
            <br />
            <span>Status</span>
          </>
        ),
        cell: ({ row: { original } }) => (
          <IPColumn
            link={original.link}
            nic={original.nic}
            node={original.machine}
          />
        ),
      },
      {
        id: "dhcp",
        enableSorting: false,
        header: () => (
          <TableHeader className="p-double-row__header-spacer">
            DHCP
          </TableHeader>
        ),
        cell: ({ row: { original } }) => <DHCPColumn nic={original.nic} />,
      },
    ],
    []
  );
};

export default useInterfaceFormTableColumns;
