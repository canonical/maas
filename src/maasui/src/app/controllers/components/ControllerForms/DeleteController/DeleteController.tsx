import type { ReactElement } from "react";

import { useDispatch, useSelector } from "react-redux";
import type { Action, Dispatch } from "redux";

import ActionForm from "@/app/base/components/ActionForm";
import NodeActionConfirmationText from "@/app/base/components/NodeActionConfirmationText";
import NodeActionWarning from "@/app/base/components/node/NodeActionWarning";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import urls from "@/app/base/urls";
import { getProcessingCount } from "@/app/controllers/utils";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors, {
  statusSelectors,
} from "@/app/store/controller/selectors";
import { ACTIONS } from "@/app/store/controller/slice";
import type { Controller } from "@/app/store/controller/types";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import { capitaliseFirst, kebabToCamelCase } from "@/app/utils";

type DeleteControllerProps = {
  controllers: Controller[];
  isViewingDetails: boolean;
};

export const DeleteController = ({
  controllers,
  isViewingDetails,
}: DeleteControllerProps): ReactElement => {
  const dispatch = useDispatch<Dispatch<Action>>();
  const actionStatus = ACTIONS.find(
    ({ name }) => name === NodeActions.DELETE
  )?.status;
  const processingControllers = useSelector(
    actionStatus ? statusSelectors[actionStatus] : () => []
  );
  const { closeSidePanel } = useSidePanel();

  const controllerSystemIds = controllers.map(({ system_id }) => system_id);
  // The form expects one error, so we only show the latest error with the
  // assumption that all selected controllers fail in the same way.
  const actionErrors = useSelector((state: RootState) =>
    controllerSelectors.eventErrorsForControllers(
      state,
      controllerSystemIds,
      kebabToCamelCase(NodeActions.DELETE)
    )
  )[0]?.error;
  const processingCount = getProcessingCount(
    controllers,
    processingControllers
  );

  const handleSubmit = () => {
    dispatch(controllerActions.cleanup());
    controllers.forEach((controller) => {
      dispatch(controllerActions.delete({ system_id: controller.system_id }));
    });
  };

  return (
    <>
      {controllers.length === 0 ? (
        <NodeActionWarning
          action={NodeActions.DELETE}
          nodeType="controller"
          selectedCount={controllers.length}
        />
      ) : null}
      <ActionForm<EmptyObject>
        actionName={NodeActions.DELETE}
        allowUnchanged
        cleanup={controllerActions.cleanup}
        errors={actionErrors}
        initialValues={{}}
        modelName="controller"
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Submit",
          category: `${capitaliseFirst("controller")} ${
            isViewingDetails ? "details" : "list"
          } action form`,
          label: "Delete",
        }}
        onSubmit={handleSubmit}
        onSuccess={() => {
          closeSidePanel();
        }}
        processingCount={processingCount}
        savedRedirect={isViewingDetails ? urls.controllers.index : undefined}
        selectedCount={controllers.length}
        submitAppearance="negative"
      >
        <NodeActionConfirmationText
          action={NodeActions.DELETE}
          modelName="controller"
          selectedCount={controllers.length}
        />
      </ActionForm>
    </>
  );
};

export default DeleteController;
