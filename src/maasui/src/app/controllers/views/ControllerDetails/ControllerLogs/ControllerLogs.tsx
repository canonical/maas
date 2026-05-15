import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import NodeLogs from "@/app/base/components/node/NodeLogs";
import { useWindowTitle } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import { isControllerDetails } from "@/app/store/controller/utils";
import type { RootState } from "@/app/store/root/types";

type Props = {
  systemId: Controller[ControllerMeta.PK];
};

export enum Label {
  Loading = "Loading logs",
}

const ControllerLogs = ({ systemId }: Props): React.ReactElement => {
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, systemId)
  );
  useWindowTitle(`${`${controller?.hostname}` || "Controller"} logs`);

  if (!controller || !isControllerDetails(controller)) {
    return <Spinner aria-label={Label.Loading} text="Loading..." />;
  }
  return (
    <NodeLogs
      node={controller}
      urls={{
        events: urls.controllers.controller.logs.events,
        index: urls.controllers.controller.logs.index,
        installationOutput: urls.controllers.controller.logs.installationOutput,
      }}
    />
  );
};

export default ControllerLogs;
