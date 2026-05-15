import { useEffect, useState } from "react";

import { useDispatch, useSelector } from "react-redux";

import DoubleRow from "@/app/base/components/DoubleRow";
import type { ControllerDetails } from "@/app/store/controller/types";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { scriptResultActions } from "@/app/store/scriptresult";
import scriptResultsSelectors from "@/app/store/scriptresult/selectors";
import type { ScriptResult } from "@/app/store/scriptresult/types";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";
import {
  getInterfaceDiscovered,
  getInterfaceFabric,
  getInterfaceIPAddressOrMode,
  getLinkInterface,
} from "@/app/store/utils";
import vlanSelectors from "@/app/store/vlan/selectors";

/**
 * Get the text for the failed status.
 * @param nic - A network interface.
 * @param failedNetworkResults - The failed network testing results.
 * @return The display text for a link mode.
 */
const getNetworkTestingStatus = (
  nic: NetworkInterface | null | undefined,
  failedNetworkResults: ScriptResult[] | null
): string | null => {
  if (!nic || !failedNetworkResults?.length) {
    return null;
  }
  const failedTests = failedNetworkResults.filter(
    (result) => result.interface?.id === nic.id
  );
  if (failedTests.length > 1) {
    return `${failedTests.length} failed tests`;
  }
  if (failedTests.length === 1) {
    return `${failedTests[0].name} failed`;
  }
  return null;
};

type Props = {
  link?: NetworkLink | null;
  nic?: NetworkInterface | null;
  node: ControllerDetails | MachineDetails;
};

const IPColumn = ({ link, nic, node }: Props): React.ReactElement | null => {
  const dispatch = useDispatch();
  const [scriptResultsRequested, setScriptResultsRequested] = useState(false);
  const fabrics = useSelector(fabricSelectors.all);
  const vlans = useSelector(vlanSelectors.all);
  const failedNetworkResults = useSelector((state: RootState) =>
    scriptResultsSelectors.getNetworkTestingByNodeId(
      state,
      node.system_id,
      true
    )
  );
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }

  useEffect(() => {
    if (!scriptResultsRequested) {
      dispatch(scriptResultActions.getByNodeId(node.system_id));
      setScriptResultsRequested(true);
    }
  }, [dispatch, node, scriptResultsRequested]);

  const fabric = getInterfaceFabric(node, fabrics, vlans, nic, link);
  const discovered = getInterfaceDiscovered(node, nic, link);

  return (
    <DoubleRow
      primary={getInterfaceIPAddressOrMode(node, fabrics, vlans, nic, link)}
      secondary={
        fabric && !discovered?.ip_address
          ? getNetworkTestingStatus(nic, failedNetworkResults)
          : null
      }
    />
  );
};

export default IPColumn;
