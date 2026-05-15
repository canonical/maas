import type { ReactNode } from "react";

import { useSelector } from "react-redux";
import { Link } from "react-router";

import DoubleRow from "@/app/base/components/DoubleRow";
import { useIsAllNetworkingDisabled } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import fabricSelectors from "@/app/store/fabric/selectors";
import subnetSelectors from "@/app/store/subnet/selectors";
import { getSubnetDisplay } from "@/app/store/subnet/utils";
import type {
  NetworkInterface,
  NetworkLink,
  Node,
} from "@/app/store/types/node";
import {
  getInterfaceDiscovered,
  getInterfaceFabric,
  getInterfaceSubnet,
  getLinkInterface,
} from "@/app/store/utils";
import vlanSelectors from "@/app/store/vlan/selectors";

type Props = {
  link?: NetworkLink | null;
  nic?: NetworkInterface | null;
  node: Node;
};

const SubnetColumn = ({
  link,
  nic,
  node,
}: Props): React.ReactElement | null => {
  const fabrics = useSelector(fabricSelectors.all);
  const subnets = useSelector(subnetSelectors.all);
  const subnetsLoaded = useSelector(subnetSelectors.loaded);
  const vlans = useSelector(vlanSelectors.all);
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(node);

  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }

  if (!subnetsLoaded) {
    return null;
  }

  const fabric = getInterfaceFabric(node, fabrics, vlans, nic, link);
  const subnet = getInterfaceSubnet(
    node,
    subnets,
    fabrics,
    vlans,
    isAllNetworkingDisabled,
    nic,
    link
  );
  const discovered = getInterfaceDiscovered(node, nic, link);
  const discoveredSubnetId = discovered?.subnet_id || null;
  const showLinkSubnet = !!fabric && !discoveredSubnetId;
  const showDiscoveredSubnet = isAllNetworkingDisabled && discoveredSubnetId;
  const subnetDisplay = getSubnetDisplay(subnet, showLinkSubnet);
  let primary: ReactNode = null;
  if (showLinkSubnet) {
    primary = subnet ? (
      <Link
        className="p-link--soft"
        to={urls.networks.subnet.index({ id: subnet.id })}
      >
        {subnetDisplay}
      </Link>
    ) : (
      subnetDisplay
    );
  } else if (showDiscoveredSubnet) {
    primary = subnetDisplay;
  } else {
    return null;
  }

  return (
    <DoubleRow
      primary={primary}
      secondary={
        showLinkSubnet && subnet ? (
          <Link
            className="p-link--muted"
            to={urls.networks.subnet.index({ id: subnet.id })}
          >
            {subnet.name}
          </Link>
        ) : null
      }
    />
  );
};

export default SubnetColumn;
