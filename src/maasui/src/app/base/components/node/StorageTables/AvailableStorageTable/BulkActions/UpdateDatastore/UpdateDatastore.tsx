import type { ReactElement } from "react";

import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import UpdateDatastoreFields from "./UpdateDatastoreFields";

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
import { isDatastore, splitDiskPartitionIds } from "@/app/store/utils";

export type UpdateDatastoreValues = {
  datastore: number;
};

type UpdateDatastoreProps = {
  selected: (Disk | Partition)[];
  systemId: Machine["system_id"];
};

const UpdateDatastoreSchema = Yup.object().shape({
  datastore: Yup.number().required("Datastore is required"),
});

export const UpdateDatastore = ({
  selected,
  systemId,
}: UpdateDatastoreProps): ReactElement | null => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "updatingVmfsDatastore",
    "updateVmfsDatastore",
    () => {
      closeSidePanel();
    }
  );

  if (isMachineDetails(machine)) {
    const datastores = machine.disks.filter((disk) =>
      isDatastore(disk.filesystem)
    );

    if (datastores.length === 0) {
      // Close the form if the last remaining datastore was deleted after the
      // form had already been opened.
      closeSidePanel();
      return null;
    }

    return (
      <FormikForm<UpdateDatastoreValues, MachineEventErrors>
        allowUnchanged
        cleanup={machineActions.cleanup}
        errors={errors}
        initialValues={{
          datastore: datastores[0].id,
        }}
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Update datastore",
          category: "Machine storage",
          label: "Add to datastore",
        }}
        onSubmit={(values: UpdateDatastoreValues) => {
          const [blockDeviceIds, partitionIds] =
            splitDiskPartitionIds(selected);
          const params = {
            systemId,
            vmfsDatastoreId: values.datastore,
            ...(blockDeviceIds.length > 0 && { blockDeviceIds }),
            ...(partitionIds.length > 0 && { partitionIds }),
          };
          dispatch(machineActions.updateVmfsDatastore(params));
        }}
        saved={saved}
        saving={saving}
        submitLabel="Add to datastore"
        validationSchema={UpdateDatastoreSchema}
      >
        <UpdateDatastoreFields
          datastores={datastores}
          storageDevices={selected}
        />
      </FormikForm>
    );
  }
  return null;
};

export default UpdateDatastore;
