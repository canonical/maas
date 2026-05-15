import type { ReactElement } from "react";

import { Col, Input, Row } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import DatastoreTable from "@/app/base/components/node/StorageTables/AvailableStorageTable/BulkActions/DatastoreTable";
import { useSidePanel } from "@/app/base/side-panel-context";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import type { Disk, Partition } from "@/app/store/types/node";
import {
  formatSize,
  isDatastore,
  splitDiskPartitionIds,
} from "@/app/store/utils";

type CreateDatastoreValues = {
  name: string;
};

type CreateDatastoreProps = {
  selected: (Disk | Partition)[];
  systemId: Machine["system_id"];
};

/**
 * Get the initial name of the datastore for the form, which is a simple count
 * of the number of existing datastores, indexed at 1 to match the api.
 * @param disks - the disks to search for datastores.
 * @returns initial name of the datastore for the form
 */
const getInitialName = (disks: Disk[]) => {
  if (!disks || disks.length === 0) {
    return "datastore1";
  }
  const datastoresCount = disks.reduce<number>(
    (count, disk) => (isDatastore(disk.filesystem) ? count + 1 : count),
    1
  );
  return `datastore${datastoresCount}`;
};

const CreateDatastoreSchema = Yup.object().shape({
  name: Yup.string().required("Name is required"),
});

export const CreateDatastore = ({
  selected,
  systemId,
}: CreateDatastoreProps): ReactElement | null => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "creatingVmfsDatastore",
    "createVmfsDatastore",
    () => {
      closeSidePanel();
    }
  );
  const totalSize = selected.reduce((sum, device) => (sum += device.size), 0);

  if (isMachineDetails(machine)) {
    return (
      <FormikForm<CreateDatastoreValues, MachineEventErrors>
        allowUnchanged
        cleanup={machineActions.cleanup}
        errors={errors}
        initialValues={{
          name: getInitialName(machine.disks),
        }}
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Create datastore",
          category: "Machine storage",
          label: "Create datastore",
        }}
        onSubmit={(values: CreateDatastoreValues) => {
          const [blockDeviceIds, partitionIds] =
            splitDiskPartitionIds(selected);
          const params = {
            name: values.name,
            systemId,
            ...(blockDeviceIds.length > 0 && { blockDeviceIds }),
            ...(partitionIds.length > 0 && { partitionIds }),
          };
          dispatch(machineActions.createVmfsDatastore(params));
        }}
        saved={saved}
        saving={saving}
        submitLabel="Create datastore"
        validationSchema={CreateDatastoreSchema}
      >
        <Row>
          <Col size={12}>
            <DatastoreTable data={selected} />
          </Col>
          <Col size={12}>
            <FormikField label="Name" name="name" required type="text" />
            <Input
              aria-label="Size"
              data-testid="datastore-size"
              disabled
              label="Size"
              type="text"
              value={`${formatSize(totalSize)}`}
            />
            <Input
              aria-label="Filesystem"
              disabled
              label="Filesystem"
              type="text"
              value="VMFS6"
            />
          </Col>
        </Row>
      </FormikForm>
    );
  }
  return null;
};

export default CreateDatastore;
