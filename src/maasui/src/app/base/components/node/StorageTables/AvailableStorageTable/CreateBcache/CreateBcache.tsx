import type { ReactElement } from "react";

import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import CreateBcacheFields from "./CreateBcacheFields";

import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import { BcacheModes } from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import type { Disk, Partition } from "@/app/store/types/node";
import { isBcache, isCacheSet, isDisk } from "@/app/store/utils";

export type CreateBcacheValues = {
  cacheMode: BcacheModes;
  cacheSetId: number;
  fstype?: string;
  mountOptions?: string;
  mountPoint?: string;
  name: string;
  tags: string[];
};

type CreateBcacheSchemaProps = {
  storageDevice: Disk | Partition;
  systemId: Machine["system_id"];
};

const CreateBcacheSchema = Yup.object().shape({
  cacheMode: Yup.string().required("Cache mode is required"),
  cacheSetId: Yup.number().required("Cache set is required"),
  fstype: Yup.string(),
  mountOptions: Yup.string(),
  mountPoint: Yup.string().when("fstype", {
    is: (val: CreateBcacheValues["fstype"]) => Boolean(val) && val !== "swap",
    then: Yup.string().matches(/^\//, "Mount point must start with /"),
  }),
  name: Yup.string().required("Name is required"),
  tags: Yup.array().of(Yup.string()),
});

const getInitialName = (disks: Disk[]) => {
  if (!disks || disks.length === 0) {
    return "bcache0";
  }
  const bcacheCount = disks.reduce<number>(
    (count, disk) => (isBcache(disk) ? count + 1 : count),
    0
  );
  return `bcache${bcacheCount}`;
};

export const CreateBcache = ({
  storageDevice,
  systemId,
}: CreateBcacheSchemaProps): ReactElement | null => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "creatingBcache",
    "createBcache",
    () => {
      closeSidePanel();
    }
  );
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );

  if (isMachineDetails(machine)) {
    const cacheSets = machine.disks.filter((disk) => isCacheSet(disk));

    if (cacheSets.length === 0) {
      // Close the form if the last remaining cache set was deleted after the
      // form had already opened.
      closeSidePanel();
      return null;
    }

    return (
      <FormikForm<CreateBcacheValues, MachineEventErrors>
        allowUnchanged
        aria-label="Create bcache form"
        cleanup={machineActions.cleanup}
        errors={errors}
        initialValues={{
          cacheMode: BcacheModes.WRITE_BACK,
          cacheSetId: cacheSets[0].id,
          fstype: "",
          mountOptions: "",
          mountPoint: "",
          name: getInitialName(machine.disks),
          tags: [],
        }}
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Create bcache",
          category: "Machine storage",
          label: "Create bcache",
        }}
        onSubmit={(values) => {
          const {
            cacheMode,
            cacheSetId,
            fstype,
            mountOptions,
            mountPoint,
            name,
            tags,
          } = values;

          const params = {
            cacheMode,
            cacheSetId: Number(cacheSetId),
            name,
            systemId: machine.system_id,
            ...(isDisk(storageDevice) && { blockId: storageDevice.id }),
            ...(fstype && { fstype }),
            ...(fstype && mountOptions && { mountOptions }),
            ...(fstype && mountPoint && { mountPoint }),
            ...(!isDisk(storageDevice) && { partitionId: storageDevice.id }),
            ...(tags.length > 0 && { tags }),
          };

          dispatch(machineActions.createBcache(params));
        }}
        saved={saved}
        saving={saving}
        submitLabel="Create bcache"
        validationSchema={CreateBcacheSchema}
      >
        <CreateBcacheFields
          cacheSets={cacheSets}
          storageDevice={storageDevice}
          systemId={systemId}
        />
      </FormikForm>
    );
  }
  return null;
};

export default CreateBcache;
