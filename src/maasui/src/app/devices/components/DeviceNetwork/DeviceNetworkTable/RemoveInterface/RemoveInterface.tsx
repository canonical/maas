import { useEffect } from "react";

import { Notification as NotificationBanner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useCycled, useSendAnalyticsWhen } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import type {
  Device,
  DeviceMeta,
  DeviceNetworkInterface,
} from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";
import { formatErrors } from "@/app/utils";

type Props = {
  nicId: DeviceNetworkInterface["id"];
  systemId: Device[DeviceMeta.PK];
};

const RemoveInterface = ({ nicId, systemId }: Props): React.ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const deletingInterface = useSelector((state: RootState) =>
    deviceSelectors.getStatusForDevice(state, systemId, "deletingInterface")
  );
  const deleteInterfaceError = useSelector((state: RootState) =>
    deviceSelectors.eventErrorsForDevices(state, systemId, "deleteInterface")
  )[0]?.error;
  const [deletedInterface] = useCycled(
    !deletingInterface && !deleteInterfaceError
  );
  useSendAnalyticsWhen(
    deletedInterface,
    "Device network",
    "Remove interface",
    "Remove"
  );
  useEffect(() => {
    if (deletedInterface) {
      closeSidePanel();
    }
  }, [closeSidePanel, deletedInterface]);

  return (
    <>
      {deleteInterfaceError ? (
        <NotificationBanner severity="negative">
          <span data-testid="error-message">
            {formatErrors(deleteInterfaceError)}
          </span>
        </NotificationBanner>
      ) : null}
      <ModelActionForm
        aria-label="Remove interface"
        initialValues={{}}
        modelType="interface"
        onCancel={closeSidePanel}
        onSubmit={() => {
          dispatch(deviceActions.cleanup());
          dispatch(
            deviceActions.deleteInterface({
              interface_id: nicId,
              system_id: systemId,
            })
          );
        }}
        saving={deletingInterface}
        submitLabel="Remove"
      />
    </>
  );
};

export default RemoveInterface;
