import { useSelector } from "react-redux";

import ControllerVLANsTable from "./ControllerVLANsTable";

import { useWindowTitle } from "@/app/base/hooks";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  systemId: Controller[ControllerMeta.PK];
};

const ControllerVLANs = ({ systemId }: Props): React.ReactElement => {
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, systemId)
  );
  useWindowTitle(`${`${controller?.hostname}` || "Controller"} VLANs`);

  return <ControllerVLANsTable systemId={systemId} />;
};

export default ControllerVLANs;
