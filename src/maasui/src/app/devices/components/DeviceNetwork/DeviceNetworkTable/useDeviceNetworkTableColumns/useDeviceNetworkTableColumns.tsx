import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import EditInterface from "../../EditInterface";
import RemoveInterface from "../RemoveInterface";

import MacAddressDisplay from "@/app/base/components/MacAddressDisplay";
import TableActions from "@/app/base/components/TableActions";
import SubnetColumn from "@/app/base/components/node/networking/SubnetColumn";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { Device, DeviceMeta } from "@/app/store/device/types";
import type { Subnet } from "@/app/store/subnet/types";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";

export type DeviceNetworkRowData = {
  id: NetworkInterface["id"];
  nic: NetworkInterface | null;
  mac_address?: string;
  link?: NetworkLink;
  ip_address?: string | null;
  ip_mode: string | null;
  subnet: Subnet | null;
  device: Device;
};

export type DeviceNetworkTableColumnDef = ColumnDef<
  DeviceNetworkRowData,
  Partial<DeviceNetworkRowData>
>;

const useDeviceNetworkTableColumns = ({
  isAllNetworkingDisabled,
  systemId,
}: {
  isAllNetworkingDisabled: boolean;
  systemId: Device[DeviceMeta.PK];
}): DeviceNetworkTableColumnDef[] => {
  const { openSidePanel } = useSidePanel();

  return useMemo(
    (): DeviceNetworkTableColumnDef[] => [
      {
        id: "mac_address",
        accessorKey: "mac_address",
        header: "Mac",
        enableSorting: true,
        cell: ({
          row: {
            original: { mac_address },
          },
        }) => <MacAddressDisplay>{mac_address}</MacAddressDisplay>,
      },
      {
        id: "subnet",
        accessorKey: "subnet",
        header: "Subnet",
        enableSorting: true,
        cell: ({
          row: {
            original: { nic, link, device },
          },
        }) => <SubnetColumn link={link} nic={nic} node={device} />,
      },
      {
        id: "ip_address",
        accessorKey: "ip_address",
        header: "IP address",
        enableSorting: true,
      },
      {
        id: "ip_mode",
        accessorKey: "ip_mode",
        header: "IP assignment",
        enableSorting: true,
      },
      {
        id: "actions",
        header: "Actions",
        enableSorting: false,
        cell: ({
          row: {
            original: { nic, link },
          },
        }) => (
          <TableActions
            deleteDisabled={isAllNetworkingDisabled}
            editDisabled={isAllNetworkingDisabled}
            onDelete={() => {
              openSidePanel({
                component: RemoveInterface,
                title: "Remove interface",
                props: {
                  nicId: nic!.id,
                  systemId,
                },
              });
            }}
            onEdit={() => {
              openSidePanel({
                component: EditInterface,
                title: "Edit interface",
                props: {
                  systemId,
                  nicId: nic?.id,
                  linkId: link?.id,
                },
              });
            }}
          />
        ),
      },
    ],
    [isAllNetworkingDisabled, openSidePanel, systemId]
  );
};

export default useDeviceNetworkTableColumns;
