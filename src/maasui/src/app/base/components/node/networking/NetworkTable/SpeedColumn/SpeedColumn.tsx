import type { ReactNode } from "react";

import DoubleRow from "@/app/base/components/DoubleRow";
import TooltipButton from "@/app/base/components/TooltipButton";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";
import {
  getLinkInterface,
  hasInterfaceType,
  isInterfaceConnected,
} from "@/app/store/utils";
import { formatSpeedUnits } from "@/app/utils";

type Props = {
  link?: NetworkLink | null;
  nic?: NetworkInterface | null;
  node: ControllerDetails | MachineDetails;
};

const SpeedColumn = ({ link, nic, node }: Props): React.ReactElement | null => {
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  if (!nic) {
    return null;
  }
  const isConnected = isInterfaceConnected(node, nic, link);
  let icon: ReactNode = null;

  if (!isConnected) {
    icon = (
      <TooltipButton
        iconName="disconnected"
        message="This interface is disconnected."
        position="top-left"
      />
    );
  }
  if (isConnected && nic.link_speed < nic.interface_speed) {
    icon = (
      <TooltipButton
        iconName="warning"
        message="Link connected to slow interface."
        position="top-left"
      />
    );
  }

  return hasInterfaceType(
    [
      NetworkInterfaceTypes.BOND,
      NetworkInterfaceTypes.BRIDGE,
      NetworkInterfaceTypes.VLAN,
    ],
    node,
    nic,
    link
  ) ? null : (
    <DoubleRow
      data-testid="speed"
      icon={icon}
      iconSpace={true}
      primary={
        <>
          {formatSpeedUnits(nic.link_speed)}/
          {formatSpeedUnits(nic.interface_speed)}
        </>
      }
    />
  );
};

export default SpeedColumn;
