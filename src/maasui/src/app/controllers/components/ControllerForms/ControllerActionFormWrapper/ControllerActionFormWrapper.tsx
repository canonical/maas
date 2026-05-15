import { useDispatch, useSelector } from "react-redux";

import SetControllerZoneForm from "../SetControllerZoneForm";
import TestControllerForm from "../TestControllerForm";

import FieldlessForm from "@/app/base/components/node/FieldlessForm";
import NodeActionFormWrapper from "@/app/base/components/node/NodeActionFormWrapper";
import type { HardwareType } from "@/app/base/enum";
import { useSidePanel } from "@/app/base/side-panel-context";
import DeleteController from "@/app/controllers/components/ControllerForms/DeleteController";
import { getProcessingCount } from "@/app/controllers/utils";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors, {
  statusSelectors,
} from "@/app/store/controller/selectors";
import { ACTIONS } from "@/app/store/controller/slice";
import type {
  Controller,
  ControllerActions,
} from "@/app/store/controller/types";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import { kebabToCamelCase } from "@/app/utils";

type Props = {
  action: ControllerActions;
  applyConfiguredNetworking?: boolean;
  hardwareType?: HardwareType;
  controllers: Controller[];
  viewingDetails: boolean;
};

export const ControllerActionFormWrapper = ({
  action,
  applyConfiguredNetworking,
  hardwareType,
  controllers,
  viewingDetails,
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const actionStatus = ACTIONS.find(({ name }) => name === action)?.status;
  const processingControllers = useSelector(
    actionStatus ? statusSelectors[actionStatus] : () => []
  );
  const { closeSidePanel } = useSidePanel();
  const controllerSystemIds = controllers.map(({ system_id }) => system_id);
  // The form expects one error, so we only show the latest error with the
  // assumption that all selected controllers fail in the same way.
  const errors = useSelector((state: RootState) =>
    controllerSelectors.eventErrorsForControllers(
      state,
      controllerSystemIds,
      kebabToCamelCase(action)
    )
  )[0]?.error;
  const processingCount = getProcessingCount(
    controllers,
    processingControllers
  );
  const commonNodeFormProps = {
    cleanup: controllerActions.cleanup,
    clearSidePanelContent: closeSidePanel,
    errors,
    modelName: "controller",
    nodes: controllers,
    processingCount,
    viewingDetails,
  };

  const getFormComponent = () => {
    switch (action) {
      case NodeActions.DELETE:
        return (
          <DeleteController
            controllers={controllers}
            isViewingDetails={viewingDetails}
          />
        );
      case NodeActions.SET_ZONE:
        return (
          <SetControllerZoneForm
            controllers={controllers}
            isViewingDetails={viewingDetails}
          />
        );
      case NodeActions.TEST:
        return (
          <TestControllerForm
            applyConfiguredNetworking={applyConfiguredNetworking}
            controllers={controllerSystemIds}
            hardwareType={hardwareType}
            isViewingDetails={viewingDetails}
          />
        );
      case NodeActions.IMPORT_IMAGES:
      case NodeActions.OFF:
      case NodeActions.ON:
      case NodeActions.OVERRIDE_FAILED_TESTING:
        return (
          <FieldlessForm
            action={action}
            actions={controllerActions}
            {...commonNodeFormProps}
          />
        );
    }
  };

  return (
    <NodeActionFormWrapper
      action={action}
      clearSidePanelContent={closeSidePanel}
      nodeType="controller"
      nodes={controllers}
      onUpdateSelected={(controllerIDs) =>
        dispatch(controllerActions.setSelected(controllerIDs))
      }
      processingCount={processingCount}
      viewingDetails={viewingDetails}
    >
      {getFormComponent()}
    </NodeActionFormWrapper>
  );
};

export default ControllerActionFormWrapper;
