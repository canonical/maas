import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import DHCPTable from "@/app/base/components/DHCPTable";
import NodeNetworkTab from "@/app/base/components/NodeNetworkTab";
import NetworkTable from "@/app/base/components/node/networking/NetworkTable";
import { useWindowTitle } from "@/app/base/hooks";
import controllerSelectors from "@/app/store/controller/selectors";
import { ControllerMeta } from "@/app/store/controller/types";
import type { Controller } from "@/app/store/controller/types";
import { isControllerDetails } from "@/app/store/controller/utils";
import type { RootState } from "@/app/store/root/types";

type Props = {
  systemId: Controller[ControllerMeta.PK];
};

const ControllerNetwork = ({ systemId }: Props): React.ReactElement => {
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, systemId)
  );
  useWindowTitle(`${`${controller?.hostname}` || "Controller"} network`);

  if (!controller || !isControllerDetails(controller)) {
    return <Spinner aria-label="Loading controller" text="Loading..." />;
  }

  return (
    <NodeNetworkTab
      aria-label="Controller network"
      dhcpTable={() => (
        <DHCPTable
          className="u-no-padding--top"
          modelName={ControllerMeta.MODEL}
          node={controller}
        />
      )}
      interfaceTable={() => <NetworkTable node={controller} />}
    />
  );
};

export default ControllerNetwork;
