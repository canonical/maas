import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import DoubleRow from "@/app/base/components/DoubleRow";
import TooltipButton from "@/app/base/components/TooltipButton";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { RootState } from "@/app/store/root/types";
import type { NetworkInterface } from "@/app/store/types/node";
import vlanSelectors from "@/app/store/vlan/selectors";
import { getDHCPStatus } from "@/app/store/vlan/utils";

type Props = {
  nic?: NetworkInterface | null;
};

const DHCPColumn = ({ nic }: Props): React.ReactElement | null => {
  const fabricsLoaded = useSelector(fabricSelectors.loaded);
  const fabrics = useSelector(fabricSelectors.all);
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, nic?.vlan_id)
  );
  const vlans = useSelector(vlanSelectors.all);
  const vlansLoaded = useSelector(vlanSelectors.loaded);
  if (!fabricsLoaded || !vlansLoaded) {
    return <Spinner />;
  }

  return (
    <DoubleRow
      data-testid="dhcp"
      icon={
        vlan && vlan.relay_vlan ? (
          <TooltipButton
            message={getDHCPStatus(vlan, vlans, fabrics, true)}
            position="btm-right"
          />
        ) : null
      }
      iconSpace={true}
      primary={getDHCPStatus(vlan, vlans, fabrics)}
    />
  );
};

export default DHCPColumn;
