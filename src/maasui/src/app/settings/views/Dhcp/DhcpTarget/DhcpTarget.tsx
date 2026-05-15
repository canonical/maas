import type { ReactNode } from "react";

import { Spinner } from "@canonical/react-components";
import { Link } from "react-router";

import urls from "@/app/base/urls";
import { useDhcpTarget } from "@/app/settings/hooks";
import type { DHCPSnippet } from "@/app/store/dhcpsnippet/types";

type Props = {
  nodeId?: DHCPSnippet["node"];
  subnetId?: DHCPSnippet["subnet"];
};

const DhcpTarget = ({ nodeId, subnetId }: Props): React.ReactElement | null => {
  const { loading, loaded, target, type } = useDhcpTarget(
    nodeId || null,
    subnetId
  );

  if (loading || !loaded) {
    return <Spinner className="u-no-margin u-no-padding" />;
  }
  if (!target) {
    return null;
  }
  let name: ReactNode = null;
  if (subnetId && "name" in target) {
    name = target.name;
  } else if ("hostname" in target) {
    name = (
      <>
        {target.hostname}
        <small>.{target.domain.name}</small>
      </>
    );
  }
  let route;
  if (type === "machine" && nodeId) {
    route = urls.machines.machine.index({ id: nodeId });
  } else if (type === "controller" && nodeId) {
    return (
      <Link to={urls.controllers.controller.index({ id: nodeId })}>{name}</Link>
    );
  } else if (type === "device" && nodeId) {
    route = urls.devices.device.index({ id: nodeId });
  } else if (type === "subnet" && subnetId) {
    route = urls.networks.subnet.index({ id: subnetId });
  }
  return route ? <Link to={route}>{name}</Link> : null;
};

export default DhcpTarget;
