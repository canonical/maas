import { Link } from "react-router";

import DoubleRow from "@/app/base/components/DoubleRow";
import urls from "@/app/base/urls";
import type { Controller } from "@/app/store/controller/types";

type Props = {
  controller: Controller;
};

// Get the HA VLAN info for a controller.
const getHaVlans = (controller: Controller) => {
  const vlansHA = controller.vlans_ha;
  return (
    [
      vlansHA?.false && `Non-HA(${vlansHA.false})`,
      vlansHA?.true && `HA(${vlansHA.true})`,
    ]
      .filter(Boolean)
      .join(", ") || null
  );
};

// Get the number of VLANs for a controller.
const getVlanCount = (controller: Controller) => {
  const vlansHA = controller.vlans_ha;
  return (vlansHA?.false || 0) + (vlansHA?.true || 0);
};

export const VLANsColumn = ({
  controller,
}: Props): React.ReactElement | null => {
  const haVlans = getHaVlans(controller);
  return (
    <DoubleRow
      primary={
        <Link
          to={urls.controllers.controller.vlans({
            id: controller.system_id,
          })}
        >
          <span data-testid="vlan-count">{getVlanCount(controller)}</span>
        </Link>
      }
      secondary={<span data-testid="ha-vlans">{haVlans}</span>}
      secondaryTitle={haVlans}
    />
  );
};

export default VLANsColumn;
