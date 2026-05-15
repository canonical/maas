import type { ReactElement } from "react";

import { useDispatch } from "react-redux";
import * as Yup from "yup";

import EditDiskFields from "./EditDiskFields";

import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import { machineActions } from "@/app/store/machine";
import type { Machine } from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import type { Disk } from "@/app/store/types/node";
import { formatType } from "@/app/store/utils";

export type EditDiskValues = {
  fstype?: string;
  mountOptions?: string;
  mountPoint?: string;
  tags: string[];
};

type EditDiskProps = {
  disk: Disk;
  systemId: Machine["system_id"];
};

const EditDiskSchema = Yup.object().shape({
  fstype: Yup.string(),
  mountOptions: Yup.string(),
  mountPoint: Yup.string().when("fstype", {
    is: (val: EditDiskValues["fstype"]) => Boolean(val) && val !== "swap",
    then: Yup.string().matches(/^\//, "Mount point must start with /"),
  }),
  tags: Yup.array().of(Yup.string()),
});

export const EditDisk = ({ disk, systemId }: EditDiskProps): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "updatingDisk",
    "updateDisk",
    () => {
      closeSidePanel();
    }
  );

  return (
    <FormikForm<EditDiskValues, MachineEventErrors>
      aria-label="Edit disk form"
      cleanup={machineActions.cleanup}
      errors={errors}
      initialValues={{
        fstype: disk.filesystem?.fstype || "",
        mountOptions: disk.filesystem?.mount_options || "",
        mountPoint: disk.filesystem?.mount_point || "",
        tags: disk.tags || [],
      }}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: `Edit ${formatType(disk, true)}`,
        category: "Machine storage",
        label: "Save",
      }}
      onSubmit={(values) => {
        const { fstype, mountOptions, mountPoint, tags } = values;
        const params = {
          blockId: disk.id,
          systemId,
          tags,
          ...(fstype && { fstype }),
          ...(fstype && mountOptions && { mountOptions }),
          ...(fstype && mountPoint && { mountPoint }),
        };

        dispatch(machineActions.updateDisk(params));
      }}
      saved={saved}
      saving={saving}
      submitLabel="Save"
      validationSchema={EditDiskSchema}
    >
      <EditDiskFields disk={disk} systemId={systemId} />
    </FormikForm>
  );
};

export default EditDisk;
