import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import ServicesCard from "./ServicesCard";

import HardwareCard from "@/app/base/components/node/HardwareCard";
import OverviewCard from "@/app/base/components/node/OverviewCard";
import { useWindowTitle } from "@/app/base/hooks";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import { isControllerDetails } from "@/app/store/controller/utils";
import type { RootState } from "@/app/store/root/types";

type Props = {
  systemId: Controller[ControllerMeta.PK];
};

const ControllerSummary = ({ systemId }: Props): React.ReactElement => {
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, systemId)
  );
  useWindowTitle(`${`${controller?.hostname}` || "Controller"} summary`);

  if (!isControllerDetails(controller)) {
    return <Spinner text="Loading..." />;
  }
  return (
    <div className="controller-summary">
      <div className="controller-summary__overview-card">
        <OverviewCard node={controller} />
      </div>
      <div className="controller-summary__services-card">
        <ServicesCard controller={controller} />
      </div>
      <div className="controller-summary__hardware-card">
        <HardwareCard node={controller} />
      </div>
    </div>
  );
};

export default ControllerSummary;
