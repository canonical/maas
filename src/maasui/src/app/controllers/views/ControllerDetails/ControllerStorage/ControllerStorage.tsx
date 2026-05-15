import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import StorageTables from "@/app/base/components/node/StorageTables";
import { useWindowTitle } from "@/app/base/hooks";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import { isControllerDetails } from "@/app/store/controller/utils";
import type { RootState } from "@/app/store/root/types";

type Props = {
  systemId: Controller[ControllerMeta.PK];
};

const ControllerStorage = ({ systemId }: Props): React.ReactElement => {
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, systemId)
  );
  useWindowTitle(`${`${controller?.hostname}` || "Controller"} storage`);

  if (isControllerDetails(controller)) {
    return <StorageTables canEditStorage={false} node={controller} />;
  }
  return <Spinner aria-label="Loading controller" text="Loading..." />;
};

export default ControllerStorage;
