import type { RefObject } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import classNames from "classnames";
import { useSelector } from "react-redux";

import type { CloneNetworkRowData } from "./useCloneNetworkTableColumns/useCloneNetworkTableColumns";
import useCloneNetworkTableColumns from "./useCloneNetworkTableColumns/useCloneNetworkTableColumns";

import { useIsAllNetworkingDisabled } from "@/app/base/hooks";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { Fabric } from "@/app/store/fabric/types";
import type { MachineDetails } from "@/app/store/machine/types";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";
import { getSubnetDisplay } from "@/app/store/subnet/utils";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";
import {
  getBondOrBridgeParents,
  getInterfaceFabric,
  getInterfaceName,
  getInterfaceNumaNodes,
  getInterfaceSubnet,
  getInterfaceTypeText,
  getLinkInterface,
  isBondOrBridgeParent,
} from "@/app/store/utils";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN } from "@/app/store/vlan/types";
import { getDHCPStatus, getVLANDisplay } from "@/app/store/vlan/utils";

type Props = {
  containerRef?: RefObject<HTMLElement | null>;
  loadingMachineDetails?: boolean;
  machine: MachineDetails | null;
  selected: boolean;
};

const generateRow = ({
  fabrics,
  isAllNetworkingDisabled,
  isParent,
  link,
  machine,
  nic,
  subnets,
  vlans,
}: {
  fabrics: Fabric[];
  isAllNetworkingDisabled: boolean;
  isParent: boolean;
  link: NetworkLink | null;
  machine: MachineDetails;
  nic: NetworkInterface | null;
  subnets: Subnet[];
  vlans: VLAN[];
}): CloneNetworkRowData => {
  if (link && !nic) {
    [nic] = getLinkInterface(machine, link);
  }
  const fabric = getInterfaceFabric(machine, fabrics, vlans, nic, link);
  const vlan = vlans.find(({ id }) => id === nic?.vlan_id);
  const subnet = getInterfaceSubnet(
    machine,
    subnets,
    fabrics,
    vlans,
    isAllNetworkingDisabled,
    nic,
    link
  );
  const nameDisplay = getInterfaceName(machine, nic, link);
  const subnetDisplay = getSubnetDisplay(subnet, true);
  const fabricDisplay = fabric?.name || "Unconfigured";
  const vlanDisplay = getVLANDisplay(vlan);
  const typeDisplay = getInterfaceTypeText(machine, nic, link, true);
  const numaDisplay = (getInterfaceNumaNodes(machine, nic) || []).join(", ");
  const dhcpDisplay = getDHCPStatus(vlan, vlans, fabrics);

  return {
    id: nic!.id,
    name: nameDisplay,
    subnet: subnetDisplay,
    fabric: fabricDisplay,
    vlan: vlanDisplay,
    type: typeDisplay,
    numaNodes: numaDisplay,
    dhcp: dhcpDisplay,
    isParent,
  };
};

export const CloneNetworkTable = ({
  containerRef,
  loadingMachineDetails = false,
  machine,
  selected,
}: Props): React.ReactElement => {
  const fabrics = useSelector(fabricSelectors.all);
  const subnets = useSelector(subnetSelectors.all);
  const vlans = useSelector(vlanSelectors.all);
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(machine);
  let rows: CloneNetworkRowData[] = [];

  const columns = useCloneNetworkTableColumns();

  if (machine) {
    rows = [];
    machine.interfaces.forEach((nic) => {
      // Childless nics are always rendered normally. Next, if the nic has any
      // parents they will be rendered right after, in order to show the
      // parent-child hierarchy. Finally, any aliases are rendered after the
      // parent-child grouping.
      if (!isBondOrBridgeParent(machine, nic)) {
        const firstLink = nic.links.length >= 1 ? nic.links[0] : null;
        const row = generateRow({
          fabrics,
          isAllNetworkingDisabled,
          isParent: false,
          link: firstLink,
          machine,
          nic: firstLink ? null : nic,
          subnets,
          vlans,
        });
        rows.push(row);

        const parents = getBondOrBridgeParents(machine, nic);
        parents.forEach((parentNic) => {
          const row = generateRow({
            fabrics,
            isAllNetworkingDisabled,
            isParent: true,
            link: null,
            machine,
            nic: parentNic,
            subnets,
            vlans,
          });
          rows.push(row);
        });

        // "links" refers to aliases, however the first link in the array is
        // an analog of the interface itself, so we only render the links from
        // the second link onward.
        if (nic.links.length >= 2) {
          nic.links.forEach((link, i) => {
            if (i > 0) {
              const row = generateRow({
                fabrics,
                isAllNetworkingDisabled,
                isParent: false,
                link,
                machine,
                nic: null,
                subnets,
                vlans,
              });
              rows.push(row);
            }
          });
        }
      }
    });
  }

  return (
    <GenericTable
      aria-label="Clone network"
      className={classNames("clone-table--network", {
        "not-selected": !selected,
      })}
      columns={columns}
      containerRef={containerRef}
      data={rows}
      isLoading={loadingMachineDetails}
      noData={machine ? "No network information detected." : null}
      variant="full-height"
    />
  );
};

export default CloneNetworkTable;
