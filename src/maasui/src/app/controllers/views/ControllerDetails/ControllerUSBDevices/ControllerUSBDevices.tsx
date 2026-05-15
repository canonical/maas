import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import NodeDevicesTable from "@/app/base/components/node/NodeDevicesTable";
import { useWindowTitle } from "@/app/base/hooks";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import { isControllerDetails } from "@/app/store/controller/utils";
import { NodeDeviceBus } from "@/app/store/nodedevice/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  systemId: Controller[ControllerMeta.PK];
};

const ControllerUSBDevices = ({ systemId }: Props): React.ReactElement => {
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, systemId)
  );
  useWindowTitle(`${`${controller?.hostname}` || "Controller"} USB devices`);

  if (isControllerDetails(controller)) {
    return <NodeDevicesTable bus={NodeDeviceBus.USB} node={controller} />;
  }
  return <Spinner aria-label="Loading controller" text="Loading..." />;
};

export default ControllerUSBDevices;
