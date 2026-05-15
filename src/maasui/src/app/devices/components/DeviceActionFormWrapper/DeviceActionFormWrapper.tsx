import type { Dispatch, ReactElement, SetStateAction } from "react";

import type { RowSelectionState } from "@tanstack/react-table";
import { useSelector } from "react-redux";

import SetZoneForm from "../SetDeviceZoneForm";

import NodeActionFormWrapper from "@/app/base/components/node/NodeActionFormWrapper";
import { useSidePanel } from "@/app/base/side-panel-context";
import DeleteDevice from "@/app/devices/components/DeleteDevice";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device, DeviceActions } from "@/app/store/device/types";
import { NodeActions } from "@/app/store/types/node";

type Props = {
  action: DeviceActions;
  devices: Device[];
  viewingDetails: boolean;
  setRowSelection?: Dispatch<SetStateAction<RowSelectionState>>;
};

export const ActionFormWrapper = ({
  action,
  devices,
  viewingDetails,
  setRowSelection,
}: Props): ReactElement => {
  const { closeSidePanel } = useSidePanel();

  const deleting = useSelector(deviceSelectors.deleting);
  const settingZone = useSelector(deviceSelectors.settingZone);

  const processingCount =
    action === NodeActions.DELETE ? deleting.length : settingZone.length;

  return (
    <NodeActionFormWrapper
      action={action}
      clearSidePanelContent={closeSidePanel}
      nodeType="device"
      nodes={devices}
      onUpdateSelected={(deviceIDs) => {
        setRowSelection &&
          setRowSelection(
            deviceIDs.reduce((acc, system_id): RowSelectionState => {
              const id = devices.find((d) => d.system_id === system_id)?.id;
              if (id === undefined) return acc;
              return { ...acc, [id.toString()]: true };
            }, {})
          );
      }}
      processingCount={processingCount}
      viewingDetails={viewingDetails}
    >
      {action === NodeActions.DELETE ? (
        <DeleteDevice devices={devices} isViewingDetails={viewingDetails} />
      ) : (
        <SetZoneForm devices={devices} isViewingDetails={viewingDetails} />
      )}
    </NodeActionFormWrapper>
  );
};

export default ActionFormWrapper;
