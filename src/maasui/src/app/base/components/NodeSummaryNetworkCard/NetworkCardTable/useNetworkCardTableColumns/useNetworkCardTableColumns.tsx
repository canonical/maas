import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import DoubleRow from "../../../DoubleRow";
import MacAddressDisplay from "../../../MacAddressDisplay";
import TooltipButton from "../../../TooltipButton";

import type { Device } from "@/app/store/device/types/base";
import type { Fabric } from "@/app/store/fabric/types";
import { getFabricDisplay } from "@/app/store/fabric/utils";
import type { MachineDetails } from "@/app/store/machine/types/base";
import type { Subnet } from "@/app/store/subnet/types";
import type { NetworkInterface } from "@/app/store/types/node";
import {
  getInterfaceIPAddressOrMode,
  getInterfaceSubnet,
} from "@/app/store/utils";
import type { VLAN } from "@/app/store/vlan/types";
import { getDHCPStatus } from "@/app/store/vlan/utils";
import { formatSpeedUnits } from "@/app/utils/formatSpeedUnits";

export type NetwordCardColumnDef = ColumnDef<
  NetworkInterface,
  Partial<NetworkInterface>
>;

type Props = {
  node: Device | MachineDetails;
  subnets: Subnet[];
  fabrics: Fabric[];
  vlans: VLAN[];
  isAllNetworkingDisabled: boolean;
};

export const useNetworkCardTableColumns = ({
  node,
  subnets,
  fabrics,
  vlans,
  isAllNetworkingDisabled,
}: Props): NetwordCardColumnDef[] => {
  return useMemo(
    (): NetwordCardColumnDef[] => [
      {
        accessorKey: "name",
        enableSorting: false,
        header: () => (
          <DoubleRow
            primary="Name"
            primaryTitle="Name"
            secondary="MAC address"
            secondaryTitle="MAC address"
          />
        ),
        cell: ({
          row: {
            original: { name, mac_address },
          },
        }) => (
          <DoubleRow
            primary={name}
            secondary={<MacAddressDisplay>{mac_address}</MacAddressDisplay>}
          />
        ),
      },
      {
        accessorKey: "ip_address",
        enableSorting: false,
        header: () => (
          <DoubleRow
            primary="IP address"
            primaryTitle="IP address"
            secondary="Subnet"
            secondaryTitle="Subnet"
          />
        ),
        cell: ({ row: { original } }) => {
          const subnet = getInterfaceSubnet(
            node,
            subnets,
            fabrics,
            vlans,
            isAllNetworkingDisabled,
            original,
            original.links ? original.links[0] : null
          );
          return (
            <DoubleRow
              primary={getInterfaceIPAddressOrMode(
                node,
                fabrics,
                vlans,
                original,
                original.links ? original.links[0] : null
              )}
              secondary={subnet?.cidr}
            />
          );
        },
      },
      {
        accessorKey: "link_speed",
        enableSorting: false,
        header: "Link speed",
        cell: ({
          row: {
            original: { link_speed },
          },
        }) => formatSpeedUnits(link_speed),
      },
      {
        accessorKey: "fabric",
        enableSorting: false,
        header: () => (
          <>
            Fabric
            <TooltipButton
              message="Untagged traffic only"
              position="top-right"
            />
          </>
        ),
        cell: ({
          row: {
            original: { vlan_id },
          },
        }) => {
          const vlan = vlans.find((vlan) => vlan.id === vlan_id);
          const fabric = vlan
            ? fabrics.find((fabric) => fabric.id === vlan.fabric)
            : null;
          return (
            <DoubleRow
              primary={getFabricDisplay(fabric) || "Unknown"}
              secondary={vlan?.name}
            />
          );
        },
      },
      {
        accessorKey: "dhcp",
        enableSorting: false,
        header: "DHCP",
        cell: ({
          row: {
            original: { vlan_id },
          },
        }) => {
          const vlan = vlans.find((vlan) => vlan.id === vlan_id);
          const dhcpStatus = getDHCPStatus(vlan, vlans, fabrics);
          return (
            <>
              {dhcpStatus}
              {dhcpStatus === "Relayed" && (
                <TooltipButton
                  className="u-nudge-right--small"
                  message={getDHCPStatus(vlan, vlans, fabrics, true)}
                  position="btm-right"
                />
              )}
            </>
          );
        },
      },
      {
        accessorKey: "sr_iov",
        enableSorting: false,
        header: "SR-IOV",
        cell: ({
          row: {
            original: { sriov_max_vf },
          },
        }) => (sriov_max_vf > 0 ? "Yes" : "No"),
      },
    ],
    [node, subnets, fabrics, vlans, isAllNetworkingDisabled]
  );
};
