import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import ControllerConfigurationForm from "./ControllerConfigurationForm";
import ControllerPowerConfiguration from "./ControllerPowerConfiguration";

import { useWindowTitle } from "@/app/base/hooks";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  systemId: Controller[ControllerMeta.PK];
};

const ControllerConfiguration = ({ systemId }: Props): React.ReactElement => {
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, systemId)
  );
  useWindowTitle(`${`${controller?.hostname}` || "Controller"} configuration`);

  if (!controller) {
    return <Spinner aria-label="loading controller configuration" />;
  }

  return (
    <>
      <ControllerConfigurationForm systemId={systemId} />
      <ControllerPowerConfiguration systemId={systemId} />
    </>
  );
};

export default ControllerConfiguration;
