import type { ReactElement } from "react";

import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import EditPartitionFields from "./EditPartitionFields";

import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import type { Disk, Partition } from "@/app/store/types/node";

export type EditPartitionValues = {
  fstype?: string;
  mountOptions?: string;
  mountPoint?: string;
};

type EditPartitionProps = {
  disk: Disk;
  partition: Partition;
  systemId: Machine["system_id"];
};

const EditPartitionSchema = Yup.object().shape({
  fstype: Yup.string(),
  mountOptions: Yup.string(),
  mountPoint: Yup.string().when("fstype", {
    is: (val: EditPartitionValues["fstype"]) => Boolean(val) && val !== "swap",
    then: Yup.string().matches(/^\//, "Mount point must start with /"),
  }),
});

export const EditPartition = ({
  disk,
  partition,
  systemId,
}: EditPartitionProps): ReactElement | null => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "updatingFilesystem",
    "updateFilesystem",
    () => {
      closeSidePanel();
    }
  );
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );

  if (isMachineDetails(machine)) {
    const fs = partition.filesystem;

    return (
      <FormikForm<EditPartitionValues, MachineEventErrors>
        aria-label="Edit partition form"
        cleanup={machineActions.cleanup}
        errors={errors}
        initialValues={{
          fstype: fs?.fstype || "",
          mountOptions: fs?.mount_options || "",
          mountPoint: fs?.mount_point || "",
        }}
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Edit partition",
          category: "Machine storage",
          label: "Save",
        }}
        onSubmit={(values) => {
          const { fstype, mountOptions, mountPoint } = values;
          const params = {
            blockId: disk.id,
            fstype,
            partitionId: partition.id,
            systemId: machine.system_id,
            ...(fstype && mountOptions && { mountOptions }),
            ...(fstype && mountPoint && { mountPoint }),
          };

          dispatch(machineActions.updateFilesystem(params));
        }}
        saved={saved}
        saving={saving}
        submitLabel="Save"
        validationSchema={EditPartitionSchema}
      >
        <EditPartitionFields partition={partition} systemId={systemId} />
      </FormikForm>
    );
  }
  return null;
};

export default EditPartition;
