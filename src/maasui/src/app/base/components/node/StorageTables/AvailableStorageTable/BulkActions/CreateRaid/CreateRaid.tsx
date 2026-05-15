import type { ReactElement } from "react";

import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import CreateRaidFields from "./CreateRaidFields";

import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { DiskTypes } from "@/app/store/types/enum";
import type { Disk, Partition } from "@/app/store/types/node";
import { isRaid, splitDiskPartitionIds } from "@/app/store/utils";

export type CreateRaidValues = {
  blockDeviceIds: number[];
  fstype?: string;
  level:
    | DiskTypes.RAID_0
    | DiskTypes.RAID_1
    | DiskTypes.RAID_5
    | DiskTypes.RAID_6
    | DiskTypes.RAID_10;
  mountOptions?: string;
  mountPoint?: string;
  name: string;
  partitionIds: number[];
  spareBlockDeviceIds: number[];
  sparePartitionIds: number[];
  tags: string[];
};

type CreateRaidProps = {
  selected: (Disk | Partition)[];
  systemId: Machine["system_id"];
};

const getInitialName = (disks: Disk[]) => {
  if (!disks || disks.length === 0) {
    return "md0";
  }
  const raidCount = disks.reduce<number>(
    (count, disk) => (isRaid(disk) ? count + 1 : count),
    0
  );
  return `md${raidCount}`;
};

const CreateRaidSchema = Yup.object().shape({
  blockDeviceIds: Yup.array().of(Yup.string()).required(),
  fstype: Yup.string(),
  level: Yup.string().required("RAID level is required"),
  mountOptions: Yup.string(),
  mountPoint: Yup.string().when("fstype", {
    is: (val: CreateRaidValues["fstype"]) => Boolean(val) && val !== "swap",
    then: Yup.string().matches(/^\//, "Mount point must start with /"),
  }),
  name: Yup.string().required("Name is required"),
  partitionIds: Yup.array().of(Yup.number()),
  spareBlockDeviceIds: Yup.array().of(Yup.number()).required(),
  sparePartitionIds: Yup.array().of(Yup.number()).required(),
  tags: Yup.array().of(Yup.string()),
});

export const CreateRaid = ({
  selected,
  systemId,
}: CreateRaidProps): ReactElement | null => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "creatingRaid",
    "createRaid",
    () => {
      closeSidePanel();
    }
  );
  const [initialBlockDevices, initialPartitions] =
    splitDiskPartitionIds(selected);

  if (isMachineDetails(machine)) {
    return (
      <FormikForm<CreateRaidValues, MachineEventErrors>
        allowUnchanged
        cleanup={machineActions.cleanup}
        errors={errors}
        initialValues={{
          blockDeviceIds: initialBlockDevices,
          fstype: "",
          level: DiskTypes.RAID_0,
          mountOptions: "",
          mountPoint: "",
          name: getInitialName(machine.disks),
          partitionIds: initialPartitions,
          spareBlockDeviceIds: [],
          sparePartitionIds: [],
          tags: [],
        }}
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Create RAID",
          category: "Machine storage",
          label: "Create RAID",
        }}
        onSubmit={(values) => {
          const {
            blockDeviceIds,
            fstype,
            level,
            mountOptions,
            mountPoint,
            name,
            partitionIds,
            spareBlockDeviceIds,
            sparePartitionIds,
            tags,
          } = values;
          dispatch(
            machineActions.createRaid({
              level,
              name,
              systemId,
              tags,
              ...(fstype && { fstype }),
              ...(fstype && mountOptions && { mountOptions }),
              ...(fstype && mountPoint && { mountPoint }),
              ...(blockDeviceIds.length > 0 && { blockDeviceIds }),
              ...(partitionIds.length > 0 && { partitionIds }),
              ...(spareBlockDeviceIds.length > 0 && { spareBlockDeviceIds }),
              ...(sparePartitionIds.length > 0 && { sparePartitionIds }),
            })
          );
        }}
        saved={saved}
        saving={saving}
        submitLabel="Create RAID"
        validationSchema={CreateRaidSchema}
      >
        <CreateRaidFields storageDevices={selected} systemId={systemId} />
      </FormikForm>
    );
  }
  return null;
};

export default CreateRaid;
