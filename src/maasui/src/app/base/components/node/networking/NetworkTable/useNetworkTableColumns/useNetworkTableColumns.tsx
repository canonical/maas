import { useMemo } from "react";

import type {
  Column,
  ColumnDef,
  Header,
  Row,
  Table,
} from "@tanstack/react-table";

import type { Selected, SetSelected } from "../../types";

import DoubleRow from "@/app/base/components/DoubleRow";
import MacAddressDisplay from "@/app/base/components/MacAddressDisplay";
import TableHeader from "@/app/base/components/TableHeader";
import DHCPColumn from "@/app/base/components/node/networking/DHCPColumn";
import FabricColumn from "@/app/base/components/node/networking/FabricColumn";
import IPColumn from "@/app/base/components/node/networking/NetworkTable/IPColumn";
import type { Network } from "@/app/base/components/node/networking/NetworkTable/NetworkTable";
import PXEColumn from "@/app/base/components/node/networking/NetworkTable/PXEColumn";
import SpeedColumn from "@/app/base/components/node/networking/NetworkTable/SpeedColumn";
import SubnetColumn from "@/app/base/components/node/networking/SubnetColumn";
import TypeColumn from "@/app/base/components/node/networking/TypeColumn";
import NetworkTableActions from "@/app/machines/views/MachineDetails/MachineNetwork/NetworkTable/NetworkTableActions";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import { nodeIsMachine } from "@/app/store/utils";

export type NetworkColumnDef = ColumnDef<Network, Partial<Network>>;

export const filterCells = (
  _: Row<Network>,
  column: Column<Network>
): boolean => {
  return !["bondOrBridge"].includes(column.id);
};

export const filterCellsAndAction = (
  _: Row<Network>,
  column: Column<Network>
): boolean => {
  return !["bondOrBridge", "actions"].includes(column.id);
};

export const filterHeaders = (header: Header<Network, unknown>): boolean =>
  header.column.id !== "bondOrBridge";

export const filterHeadersAndAction = (
  header: Header<Network, unknown>
): boolean => !["bondOrBridge", "actions"].includes(header.column.id);

const useNetworkTableColumns = ({
  node,
  setSelected,
}: {
  node: ControllerDetails | MachineDetails;
  setSelected?: SetSelected | undefined;
}): NetworkColumnDef[] => {
  return useMemo(
    () => [
      {
        id: "bondOrBridge",
        accessorKey: "bondOrBridge",
      },
      {
        id: "name",
        accessorKey: "name",
        enableSorting: true,
        header: () => (
          <div>
            <TableHeader sortKey="name">Name</TableHeader>
            <TableHeader>MAC</TableHeader>
          </div>
        ),
        cell: ({
          row: {
            original: { name, nic },
          },
        }: {
          row: Row<Network>;
        }) => (
          <DoubleRow
            primary={<span data-testid="name">{name}</span>}
            secondary={<MacAddressDisplay>{nic.mac_address}</MacAddressDisplay>}
          />
        ),
      },
      {
        id: "pxe",
        accessorKey: "pxe",
        enableSorting: true,
        header: "PXE",
        cell: ({
          row: {
            original: { isABondOrBridgeParent, nic, link },
          },
        }: {
          row: Row<Network>;
        }) =>
          !isABondOrBridgeParent && (
            <PXEColumn link={link} nic={nic} node={node} />
          ),
      },
      {
        id: "speed",
        accessorKey: "speed",
        enableSorting: true,
        header: () => (
          <div className="p-double-row__header-spacer">
            Link/Interface Speed
          </div>
        ),
        cell: ({
          row: {
            original: { nic, link },
          },
        }: {
          row: Row<Network>;
        }) => <SpeedColumn link={link} nic={nic} node={node} />,
      },
      {
        id: "type",
        accessorKey: "type",
        enableSorting: true,
        header: () => (
          <div className="p-double-row__header-spacer">
            <TableHeader sortKey="type">Type</TableHeader>
            <TableHeader>NUMA Node</TableHeader>
          </div>
        ),
        cell: ({
          row: {
            original: { nic, link },
          },
        }: {
          row: Row<Network>;
        }) => <TypeColumn link={link} nic={nic} node={node} />,
      },
      {
        id: "fabric",
        accessorKey: "fabric",
        enableSorting: true,
        header: () => (
          <div>
            <TableHeader sortKey="fabric">Fabric</TableHeader>
            <TableHeader>VLAN</TableHeader>
          </div>
        ),
        cell: ({
          row: {
            original: { isABondOrBridgeParent, nic, link },
          },
        }: {
          row: Row<Network>;
        }) =>
          !isABondOrBridgeParent && (
            <FabricColumn link={link} nic={nic} node={node} />
          ),
      },
      {
        id: "subnet",
        accessorKey: "subnet",
        enableSorting: true,
        header: () => (
          <div>
            <TableHeader sortKey="subnet">Subnet</TableHeader>
            <TableHeader>Subnet Name</TableHeader>
          </div>
        ),
        cell: ({
          row: {
            original: { isABondOrBridgeParent, nic, link },
          },
        }: {
          row: Row<Network>;
        }) =>
          !isABondOrBridgeParent && (
            <SubnetColumn link={link} nic={nic} node={node} />
          ),
      },
      {
        id: "ip",
        accessorKey: "ip",
        enableSorting: true,
        header: () => (
          <div>
            <TableHeader sortKey="ip">IP Address</TableHeader>
            <TableHeader>Status</TableHeader>
          </div>
        ),
        cell: ({
          row: {
            original: { isABondOrBridgeParent, nic, link },
          },
        }: {
          row: Row<Network>;
        }) =>
          !isABondOrBridgeParent && (
            <IPColumn link={link} nic={nic} node={node} />
          ),
      },
      {
        id: "dhcp",
        accessorKey: "dhcp",
        enableSorting: true,
        header: () => <div className="p-double-row__header-spacer">DHCP</div>,
        cell: ({
          row: {
            original: { isABondOrBridgeParent, nic },
          },
        }: {
          row: Row<Network>;
        }) => !isABondOrBridgeParent && <DHCPColumn nic={nic} />,
      },
      {
        id: "actions",
        accessorKey: "id",
        enableSorting: false,
        header: "Actions",
        cell: ({
          row: {
            original: { isABondOrBridgeParent, nic, link },
          },
          table,
        }: {
          row: Row<Network>;
          table: Table<Network>;
        }) => {
          return !isABondOrBridgeParent && nodeIsMachine(node) ? (
            <NetworkTableActions
              link={link}
              nic={nic}
              selected={table.getSelectedRowModel().flatRows.map(
                (row): Selected => ({
                  linkId: row.original.link?.id,
                  nicId: row.original.nic.id,
                })
              )}
              setSelected={setSelected}
              systemId={node.system_id}
            />
          ) : null;
        },
      },
    ],
    [node, setSelected]
  );
};

export default useNetworkTableColumns;
