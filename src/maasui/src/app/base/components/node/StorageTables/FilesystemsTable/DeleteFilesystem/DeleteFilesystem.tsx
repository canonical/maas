import type { ReactElement } from "react";

import { useDispatch } from "react-redux";

import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { machineActions } from "@/app/store/machine";
import type { Machine } from "@/app/store/machine/types";
import type { Disk, Partition } from "@/app/store/types/node";
import { isDisk, isMounted } from "@/app/store/utils";

type DeleteFilesystemProps = {
  systemId: Machine["system_id"];
  storageDevice: Disk | Partition;
};

const DeleteFilesystem = ({
  systemId,
  storageDevice,
}: DeleteFilesystemProps): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const deviceIsDisk = isDisk(storageDevice);
  const storageFs = storageDevice.filesystem;
  const isDiskFsDelete = deviceIsDisk && isMounted(storageFs);

  return (
    <ModelActionForm
      aria-label="Delete filesystem"
      initialValues={{}}
      message={<>Are you sure you want to remove this filesystem?</>}
      modelType="filesystem"
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: `Delete ${isDiskFsDelete ? "disk" : "partition"} filesystem`,
        category: "Machine storage",
        label: "Remove",
      }}
      onSubmit={() => {
        dispatch(machineActions.cleanup());
        if (isDiskFsDelete) {
          dispatch(
            machineActions.deleteFilesystem({
              blockDeviceId: storageDevice.id,
              filesystemId: storageFs.id,
              systemId,
            })
          );
        } else {
          dispatch(
            machineActions.deletePartition({
              partitionId: storageDevice.id,
              systemId,
            })
          );
        }
        closeSidePanel();
      }}
      submitAppearance="negative"
      submitLabel="Remove"
    />
  );
};

export default DeleteFilesystem;
