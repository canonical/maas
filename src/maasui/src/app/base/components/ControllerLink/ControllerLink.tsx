import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import { useFetchActions } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  systemId?: Controller[ControllerMeta.PK] | null;
};

export enum Labels {
  LoadingControllers = "Loading controllers",
}

const ControllerLink = ({ systemId }: Props): React.ReactElement | null => {
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, systemId)
  );
  const controllersLoading = useSelector(controllerSelectors.loading);

  useFetchActions([controllerActions.fetch]);

  if (controllersLoading) {
    return <Spinner aria-label={Labels.LoadingControllers} />;
  }
  if (!controller) {
    return null;
  }
  return (
    <Link to={urls.controllers.controller.index({ id: controller.system_id })}>
      <strong>{controller.hostname}</strong>
      <span>.{controller.domain.name}</span>
    </Link>
  );
};

export default ControllerLink;
