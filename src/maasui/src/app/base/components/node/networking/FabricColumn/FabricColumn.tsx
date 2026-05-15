import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import DoubleRow from "@/app/base/components/DoubleRow";
import subnetURLs from "@/app/networks/urls";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { RootState } from "@/app/store/root/types";
import type {
  NetworkInterface,
  NetworkLink,
  Node,
} from "@/app/store/types/node";
import { getInterfaceFabric, isBondOrBridgeParent } from "@/app/store/utils";
import vlanSelectors from "@/app/store/vlan/selectors";
import { getVLANDisplay } from "@/app/store/vlan/utils";

type Props = {
  link?: NetworkLink | null;
  nic?: NetworkInterface | null;
  node: Node;
};

const FabricColumn = ({
  link,
  nic,
  node,
}: Props): React.ReactElement | null => {
  const fabricsLoaded = useSelector(fabricSelectors.loaded);
  const fabrics = useSelector(fabricSelectors.all);
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, nic?.vlan_id)
  );
  const vlans = useSelector(vlanSelectors.all);
  if (!fabricsLoaded) {
    return <Spinner />;
  }
  const isABondOrBridgeParent = isBondOrBridgeParent(node, nic, link);
  const fabric = getInterfaceFabric(node, fabrics, vlans, nic, link);
  const fabricContent = !isABondOrBridgeParent
    ? fabric?.name || "Disconnected"
    : null;

  return (
    <DoubleRow
      data-testid="fabric"
      primary={
        fabric ? (
          <Link
            className="p-link--soft"
            to={subnetURLs.fabric.index({ id: fabric.id })}
          >
            {fabricContent}
          </Link>
        ) : (
          fabricContent
        )
      }
      secondary={
        vlan ? (
          <Link
            className="p-link--muted"
            to={subnetURLs.vlan.index({ id: vlan.id })}
          >
            {getVLANDisplay(vlan)}
          </Link>
        ) : null
      }
    />
  );
};

export default FabricColumn;
