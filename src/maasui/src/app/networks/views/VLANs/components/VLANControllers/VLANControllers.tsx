import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import ControllerLink from "@/app/base/components/ControllerLink";
import Definition from "@/app/base/components/Definition";
import TooltipButton from "@/app/base/components/TooltipButton";
import controllerSelectors from "@/app/store/controller/selectors";
import type { RootState } from "@/app/store/root/types";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN, VLANMeta } from "@/app/store/vlan/types";

type Props = {
  id: VLAN[VLANMeta.PK] | null;
};

const getRackIDs = (vlan: VLAN | null) => {
  const rackIDs = [];
  if (vlan) {
    if (vlan.primary_rack) {
      rackIDs.push(vlan.primary_rack);
    }
    if (vlan.secondary_rack) {
      rackIDs.push(vlan.secondary_rack);
    }
  }
  return rackIDs;
};

const VLANControllers = ({ id }: Props): React.ReactElement | null => {
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, id)
  );
  const controllersLoading = useSelector(controllerSelectors.loading);

  if (!vlan) {
    return null;
  }

  const rackIDs = getRackIDs(vlan);
  return (
    <Definition
      label={
        <>
          Rack controllers
          <TooltipButton
            className="u-nudge-right--small"
            message={`A rack controller controls hosts and images and runs
            network services like DHCP for connected VLANs.`}
          />
        </>
      }
    >
      {controllersLoading ? (
        <span data-testid="Spinner">
          <Spinner />
        </span>
      ) : (
        rackIDs.map((rackID) => (
          <ControllerLink key={rackID} systemId={rackID} />
        ))
      )}
    </Definition>
  );
};

export default VLANControllers;
