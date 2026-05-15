import type { ReactElement } from "react";

import { useDispatch, useSelector } from "react-redux";
import type { Action, Dispatch } from "redux";

import ActionForm from "@/app/base/components/ActionForm";
import NodeActionConfirmationText from "@/app/base/components/NodeActionConfirmationText";
import NodeActionWarning from "@/app/base/components/node/NodeActionWarning";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import urls from "@/app/base/urls";
import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import { capitaliseFirst, kebabToCamelCase } from "@/app/utils";

type DeleteDeviceProps = {
  devices: Device[];
  isViewingDetails: boolean;
};

export const DeleteDevice = ({
  devices,
  isViewingDetails,
}: DeleteDeviceProps): ReactElement => {
  const dispatch = useDispatch<Dispatch<Action>>();
  const { closeSidePanel } = useSidePanel();
  const deleting = useSelector(deviceSelectors.deleting);

  // The form expects one error, so we only show the latest error with the
  // assumption that all selected devices fail in the same way.
  const actionErrors = useSelector((state: RootState) =>
    deviceSelectors.eventErrorsForDevices(
      state,
      devices.map(({ system_id }) => system_id),
      kebabToCamelCase(NodeActions.DELETE)
    )
  )[0]?.error;
  const processingCount = deleting.length;

  const handleSubmit = () => {
    dispatch(deviceActions.cleanup());
    devices.forEach((device) => {
      dispatch(deviceActions.delete({ system_id: device.system_id }));
    });
  };

  return (
    <>
      {devices.length === 0 ? (
        <NodeActionWarning
          action={NodeActions.DELETE}
          nodeType="device"
          selectedCount={devices.length}
        />
      ) : null}
      <ActionForm<EmptyObject>
        actionName={NodeActions.DELETE}
        allowUnchanged
        cleanup={deviceActions.cleanup}
        errors={actionErrors}
        initialValues={{}}
        modelName="device"
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Submit",
          category: `${capitaliseFirst("device")} ${
            isViewingDetails ? "details" : "list"
          } action form`,
          label: "Delete",
        }}
        onSubmit={handleSubmit}
        onSuccess={() => {
          closeSidePanel();
        }}
        processingCount={processingCount}
        savedRedirect={isViewingDetails ? urls.devices.index : undefined}
        selectedCount={devices.length}
        submitAppearance="negative"
      >
        <NodeActionConfirmationText
          action={NodeActions.DELETE}
          modelName="device"
          selectedCount={devices.length}
        />
      </ActionForm>
    </>
  );
};

export default DeleteDevice;
