import type { ReactElement } from "react";

import { formatBytes } from "@canonical/maas-react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import AddLogicalVolumeFields from "./AddLogicalVolumeFields";

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

export type AddLogicalVolumeValues = {
  fstype?: string;
  mountOptions?: string;
  mountPoint?: string;
  name: string;
  size: number;
  tags: string[];
  unit: string;
};

type AddLogicalVolumeProps = {
  disk: Disk;
  systemId: Machine["system_id"];
};

const generateSchema = (availableSize: number) =>
  Yup.object().shape({
    fstype: Yup.string(),
    mountOptions: Yup.string(),
    mountPoint: Yup.string().when("fstype", {
      is: (val: AddLogicalVolumeValues["fstype"]) =>
        Boolean(val) && val !== "swap",
      then: Yup.string().matches(/^\//, "Mount point must start with /"),
    }),
    name: Yup.string().required("Name is required"),
    size: Yup.number()
      .required("Size is required")
      .min(0, "Size must be greater than 0")
      .test("enoughSpace", "Not enough space", function test() {
        const values: AddLogicalVolumeValues = this.parent;
        const { size, unit } = values;
        const sizeInBytes = formatBytes(
          { value: size, unit: unit },
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
            message: `At least ${min}${unit} is required to add a logical volume`,
            path: "size",
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
            message: `Only ${max}${unit} available in this volume group`,
            path: "size",
          });
        }

        return true;
      }),
    tags: Yup.array().of(Yup.string()),
    unit: Yup.string().required(),
  });

export const AddLogicalVolume = ({
  disk,
  systemId,
}: AddLogicalVolumeProps): ReactElement | null => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "creatingLogicalVolume",
    "createLogicalVolume",
    () => {
      closeSidePanel();
    }
  );
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );

  if (isMachineDetails(machine)) {
    const initialName = `lv${machine.disks.reduce(
      (sum, d) => (d.parent?.id === disk.id ? sum + 1 : sum),
      0
    )}`;
    const AddLogicalVolumeSchema = generateSchema(disk.available_size);

    return (
      <FormikForm<AddLogicalVolumeValues, MachineEventErrors>
        allowUnchanged
        aria-label="Add logical volume form"
        cleanup={machineActions.cleanup}
        errors={errors}
        initialValues={{
          fstype: "",
          mountOptions: "",
          mountPoint: "",
          name: initialName,
          size: formatBytes(
            { value: disk.available_size, unit: "B" },
            {
              convertTo: "GB",
              roundFunc: "floor",
            }
          ).value,
          tags: [],
          unit: "GB",
        }}
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Add logical volume",
          category: "Machine storage",
          label: "Add logical volume",
        }}
        onSubmit={(values: AddLogicalVolumeValues) => {
          const { fstype, mountOptions, mountPoint, name, size, tags, unit } =
            values;
          // Convert size into bytes before dispatching action
          const convertedSize = formatBytes(
            { value: size, unit: unit },
            {
              convertTo: "B",
            }
          )?.value;
          const params = {
            name,
            size: convertedSize,
            systemId: machine.system_id,
            volumeGroupId: disk.id,
            ...(fstype && { fstype }),
            ...(fstype && mountOptions && { mountOptions }),
            ...(fstype && mountPoint && { mountPoint }),
            ...(tags.length > 0 && { tags }),
          };

          dispatch(machineActions.createLogicalVolume(params));
        }}
        saved={saved}
        saving={saving}
        submitLabel="Add logical volume"
        validationSchema={AddLogicalVolumeSchema}
      >
        <AddLogicalVolumeFields systemId={systemId} />
      </FormikForm>
    );
  }
  return null;
};

export default AddLogicalVolume;
