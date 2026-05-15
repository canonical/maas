import type { ReactElement } from "react";

import { formatBytes } from "@canonical/maas-react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import AddPartitionFields from "./AddPartitionFields";

import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import { machineActions } from "@/app/store/machine";
import { MIN_PARTITION_SIZE } from "@/app/store/machine/constants";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import type { Disk } from "@/app/store/types/node";

export type AddPartitionValues = {
  fstype?: string;
  mountOptions?: string;
  mountPoint?: string;
  partitionSize: number;
  unit: string;
};

type AddPartitionProps = {
  disk: Disk;
  systemId: Machine["system_id"];
};

const generateSchema = (availableSize: number) =>
  Yup.object().shape({
    fstype: Yup.string(),
    mountOptions: Yup.string(),
    mountPoint: Yup.string().when("fstype", {
      is: (val: AddPartitionValues["fstype"]) => Boolean(val) && val !== "swap",
      then: Yup.string().matches(/^\//, "Mount point must start with /"),
    }),
    partitionSize: Yup.number()
      .required("Size is required")
      .min(0, "Size must be greater than 0")
      .test("enoughSpace", "Not enough space", function test() {
        const values: AddPartitionValues = this.parent;
        const { partitionSize, unit } = values;
        const sizeInBytes = formatBytes(
          { value: partitionSize, unit },
          {
            convertTo: "B",
            roundFunc: "floor",
          }
        ).value;

        if (sizeInBytes < MIN_PARTITION_SIZE) {
          const min = formatBytes(
            { value: MIN_PARTITION_SIZE, unit: "B" },
            {
              convertTo: unit,
              roundFunc: "floor",
            }
          ).value;
          return this.createError({
            message: `At least ${min}${unit} is required to partition this disk`,
            path: "partitionSize",
          });
        }

        if (sizeInBytes > availableSize) {
          const max = formatBytes(
            { value: availableSize, unit: "B" },
            {
              convertTo: unit,
              roundFunc: "floor",
            }
          ).value;
          return this.createError({
            message: `Only ${max}${unit} available in this disk`,
            path: "partitionSize",
          });
        }

        return true;
      }),
    unit: Yup.string().required(),
  });

export const AddPartition = ({
  disk,
  systemId,
}: AddPartitionProps): ReactElement | null => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "creatingPartition",
    "createPartition",
    () => {
      closeSidePanel();
    }
  );
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );

  if (isMachineDetails(machine)) {
    const partitionName = disk
      ? `${disk.name}-part${(disk.partitions?.length || 0) + 1}`
      : "partition";
    const AddPartitionSchema = generateSchema(disk.available_size);

    return (
      <FormikForm<AddPartitionValues, MachineEventErrors>
        allowUnchanged
        aria-label="Add partition form"
        cleanup={machineActions.cleanup}
        errors={errors}
        initialValues={{
          fstype: "",
          mountOptions: "",
          mountPoint: "",
          partitionSize: formatBytes(
            { value: disk.available_size, unit: "B" },
            {
              convertTo: "GB",
              roundFunc: "floor",
            }
          ).value,
          unit: "GB",
        }}
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Add partition",
          category: "Machine storage",
          label: "Add partition",
        }}
        onSubmit={(values) => {
          dispatch(machineActions.cleanup());
          const { fstype, mountOptions, mountPoint, partitionSize, unit } =
            values;
          // Convert size into bytes before dispatching action
          const size = formatBytes(
            { value: partitionSize, unit },
            {
              convertTo: "B",
            }
          )?.value;
          const params = {
            blockId: disk.id,
            partitionSize: size,
            systemId: machine.system_id,
            ...(fstype && { fstype }),
            ...(fstype && mountOptions && { mountOptions }),
            ...(fstype && mountPoint && { mountPoint }),
          };

          dispatch(machineActions.createPartition(params));
        }}
        saved={saved}
        saving={saving}
        submitLabel="Add partition"
        validationSchema={AddPartitionSchema}
      >
        <AddPartitionFields partitionName={partitionName} systemId={systemId} />
      </FormikForm>
    );
  }
  return null;
};

export default AddPartition;
