import { Notification as NotificationBanner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import { useIsRackControllerConnected } from "@/app/base/hooks";
import type { ControllerDetails } from "@/app/store/controller/types";
import { PowerTypeNames } from "@/app/store/general/constants";
import { powerTypes as powerTypesSelectors } from "@/app/store/general/selectors";
import { getPowerTypeFromName } from "@/app/store/general/utils";
import type { MachineDetails } from "@/app/store/machine/types";

type Props = {
  node: ControllerDetails | MachineDetails;
};

const NodePowerNotifications = ({ node }: Props): React.ReactElement => {
  const powerTypes = useSelector(powerTypesSelectors.get);
  const isRackControllerConnected = useIsRackControllerConnected();
  const powerType = getPowerTypeFromName(powerTypes, node.power_type);

  return (
    <>
      {!isRackControllerConnected && (
        <NotificationBanner
          data-testid="no-rack-controller"
          severity="negative"
        >
          Power configuration is currently disabled because no rack controller
          is currently connected to the region.
        </NotificationBanner>
      )}
      {isRackControllerConnected && !powerType && (
        <NotificationBanner data-testid="no-power-type" severity="negative">
          This node does not have a power type set and MAAS will be unable to
          control it. Update the power information below.
        </NotificationBanner>
      )}
      {powerType?.name === PowerTypeNames.MANUAL && (
        <NotificationBanner data-testid="manual-power-type" severity="caution">
          Power control for this power type will need to be handled manually.
        </NotificationBanner>
      )}
      {powerType && powerType.missing_packages.length > 0 && (
        <NotificationBanner data-testid="missing-packages" severity="negative">
          Power control software for {powerType.description} is missing from the
          rack controller. To proceed, install the following packages on the
          rack controller: {powerType.missing_packages.join(", ")}
        </NotificationBanner>
      )}
    </>
  );
};

export default NodePowerNotifications;
