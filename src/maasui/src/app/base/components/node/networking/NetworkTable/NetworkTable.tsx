import type { ReactElement } from "react";
import { useEffect, useMemo, useState } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import type { RowSelectionState } from "@tanstack/react-table";
import classNames from "classnames";
import { useSelector } from "react-redux";

import type { SetExpanded } from "@/app/base/components/NodeNetworkTab/NodeNetworkTab";
import useNetworkTableColumns, {
  filterCells,
  filterCellsAndAction,
  filterHeaders,
  filterHeadersAndAction,
} from "@/app/base/components/node/networking/NetworkTable/useNetworkTableColumns/useNetworkTableColumns";
import type {
  Selected,
  SetSelected,
} from "@/app/base/components/node/networking/types";
import { useFetchActions, useIsAllNetworkingDisabled } from "@/app/base/hooks";
import type { ControllerDetails } from "@/app/store/controller/types";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { Fabric } from "@/app/store/fabric/types";
import type { MachineDetails } from "@/app/store/machine/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";
import { getSubnetDisplay } from "@/app/store/subnet/utils";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";
import {
  getInterfaceFabric,
  getInterfaceIPAddressOrMode,
  getInterfaceName,
  getInterfaceSubnet,
  getInterfaceTypeText,
  getLinkInterface,
  isBondOrBridgeChild,
  isBondOrBridgeParent,
  isBootInterface,
} from "@/app/store/utils";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN } from "@/app/store/vlan/types";
import { getDHCPStatus } from "@/app/store/vlan/utils";

export type Network = {
  id: string;
  bondOrBridge: NetworkInterface["id"] | null;
  dhcp: string | null;
  fabric: string | null;
  ip: string | null;
  isABondOrBridgeChild: boolean;
  isABondOrBridgeParent: boolean;
  name: NetworkInterface["name"];
  pxe: boolean;
  speed: NetworkInterface["link_speed"];
  subnet: string | null;
  type: string | null;
  nic: NetworkInterface;
  link: NetworkLink | null;
  children?: Network[];
};

type BaseProps = {
  node: ControllerDetails | MachineDetails;
};

type ActionProps = BaseProps & {
  setExpanded?: SetExpanded;
  setSelected?: SetSelected;
};

type WithoutActionProps = BaseProps & {
  setExpanded?: never;
  setSelected?: never;
};

type Props = ActionProps | WithoutActionProps;

export const generateUniqueId = ({ linkId, nicId }: Selected): string =>
  `${nicId || ""}-${linkId || ""}`;

const getNetworkTableData = (
  fabrics: Fabric[],
  fabricsLoaded: boolean,
  isAllNetworkingDisabled: boolean,
  node: ControllerDetails | MachineDetails,
  subnets: Subnet[],
  vlans: VLAN[],
  vlansLoaded: boolean
) => {
  const flatNetworks: Network[] = [];
  node.interfaces.forEach((nic: NetworkInterface) => {
    const createNetwork = (
      link: NetworkLink | null,
      nic: NetworkInterface | null
    ): Network | null => {
      if (link && !nic) {
        [nic] = getLinkInterface(node, link);
      }
      if (!nic) {
        return null;
      }
      const isABondOrBridgeParent = isBondOrBridgeParent(node, nic, link);
      const isABondOrBridgeChild = isBondOrBridgeChild(node, nic, link);
      const isBoot = isBootInterface(node, nic, link);
      const vlan = vlans.find(({ id }) => id === nic?.vlan_id);
      const fabric = getInterfaceFabric(node, fabrics, vlans, nic, link);
      const name = getInterfaceName(node, nic, link);
      const interfaceTypeDisplay = getInterfaceTypeText(node, nic, link, true);
      const shouldShowDHCP =
        !isABondOrBridgeParent && fabricsLoaded && vlansLoaded;
      const fabricContent = !isABondOrBridgeParent
        ? fabric?.name || "Disconnected"
        : null;
      const subnet = getInterfaceSubnet(
        node,
        subnets,
        fabrics,
        vlans,
        isAllNetworkingDisabled,
        nic,
        link
      );
      return {
        id: generateUniqueId({ linkId: link?.id, nicId: nic?.id }),
        bondOrBridge:
          (nic &&
            ((isABondOrBridgeParent && nic.children[0]) ||
              (isABondOrBridgeChild && nic.id))) ||
          null,
        dhcp: shouldShowDHCP ? getDHCPStatus(vlan, vlans, fabrics) : null,
        fabric: fabricContent,
        ip:
          getInterfaceIPAddressOrMode(node, fabrics, vlans, nic, link) || null,
        isABondOrBridgeChild,
        isABondOrBridgeParent,
        name: name,
        pxe: isBoot,
        speed: nic.link_speed,
        subnet: getSubnetDisplay(subnet),
        type: interfaceTypeDisplay,
        nic: nic,
        link: link,
      };
    };
    if (nic.links.length === 0) {
      const network = createNetwork(null, nic);
      if (network) {
        flatNetworks.push(network);
      }
    } else {
      nic.links.forEach((link: NetworkLink) => {
        const network = createNetwork(link, null);
        if (network) {
          flatNetworks.push(network);
        }
      });
    }
  });

  const nestedNetworks: Network[] = [];
  const childIds = new Set<string>();

  flatNetworks.forEach((network) => {
    if (network.isABondOrBridgeChild) {
      const children = flatNetworks.filter(
        (n) =>
          n.isABondOrBridgeParent && n.bondOrBridge === network.bondOrBridge
      );
      if (children.length > 0) {
        network.children = children;
        children.forEach((c) => childIds.add(c.id));
      }
      nestedNetworks.push(network);
    }
  });

  flatNetworks.forEach((network) => {
    if (!network.isABondOrBridgeChild && !childIds.has(network.id)) {
      nestedNetworks.push(network);
    }
  });

  return nestedNetworks;
};

const extractSelected = (
  data: Network[],
  rowSelection: RowSelectionState
): Selected[] => {
  const pick = (network: Network) => ({
    linkId: network.link ? network.link.id : null,
    nicId: network.nic ? network.nic.id : null,
  });

  const result: Selected[] = [];
  const ids = Object.entries(rowSelection)
    .filter(([_, value]) => value)
    .map(([key]) => key);

  data.forEach((item) => {
    if (ids.includes(item.id)) {
      result.push(pick(item));
    }
  });

  return result;
};

const NetworkTable = ({
  node,
  setExpanded,
  setSelected,
}: Props): ReactElement => {
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const fabrics = useSelector(fabricSelectors.all);
  const subnets = useSelector(subnetSelectors.all);
  const vlans = useSelector(vlanSelectors.all);
  const fabricsLoaded = useSelector(fabricSelectors.loaded);
  const vlansLoaded = useSelector(vlanSelectors.loaded);
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(node);
  const hasActions = !!setExpanded;

  useFetchActions([
    fabricActions.fetch,
    subnetActions.fetch,
    vlanActions.fetch,
  ]);

  const columns = useNetworkTableColumns({ node, setSelected });
  const data = useMemo(
    () =>
      getNetworkTableData(
        fabrics,
        fabricsLoaded,
        isAllNetworkingDisabled,
        node,
        subnets,
        vlans,
        vlansLoaded
      ),
    [
      fabrics,
      fabricsLoaded,
      isAllNetworkingDisabled,
      node,
      subnets,
      vlans,
      vlansLoaded,
    ]
  );

  useEffect(
    () => {
      if (setSelected) {
        setSelected(extractSelected(data, rowSelection));
      }
    },
    // adding missing dependencies causes infinite re-render, only row selection should update selected
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rowSelection]
  );

  return (
    <GenericTable
      className={classNames("p-table-expanding--light", "network-table", {
        "network-table--has-actions": hasActions,
      })}
      columns={columns}
      data={data}
      filterCells={!!setExpanded ? filterCells : filterCellsAndAction}
      filterHeaders={!!setExpanded ? filterHeaders : filterHeadersAndAction}
      getSubRows={(originalRow) => originalRow.children}
      isLoading={!fabricsLoaded || !vlansLoaded}
      noData={"No interfaces available."}
      selection={{
        rowSelection,
        setRowSelection,
        filterSelectable: (_) => !isAllNetworkingDisabled,
        disabledSelectionTooltip: "Network can't be modified for this machine.",
        rowSelectionLabelKey: "name",
      }}
      sorting={[{ id: "name", desc: false }]}
    />
  );
};

export default NetworkTable;
