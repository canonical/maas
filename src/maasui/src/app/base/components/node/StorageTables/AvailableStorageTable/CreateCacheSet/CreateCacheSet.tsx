import type { ReactElement } from "react";

import { useDispatch } from "react-redux";

import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { machineActions } from "@/app/store/machine";
import type { Machine } from "@/app/store/machine/types";
import type { Disk, Partition } from "@/app/store/types/node";

type CreateCacheSetProps = {
  systemId: Machine["system_id"];
  diskId?: Disk["id"];
  partitionId?: Partition["id"];
};

const CreateCacheSet = ({
  systemId,
  diskId,
  partitionId,
}: CreateCacheSetProps): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const isDiskCacheSet = !!diskId;
  return (
    <ModelActionForm
      aria-label="Create cache set"
      initialValues={{}}
      message={<>Are you sure you want to create a cache set?</>}
      modelType="cache set"
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: `Create cache set from ${
          isDiskCacheSet ? "disk" : "partition"
        }`,
        category: "Machine storage",
        label: "Create cache set",
      }}
      onSubmit={() => {
        dispatch(machineActions.cleanup());
        dispatch(
          machineActions.createCacheSet({
            blockId: isDiskCacheSet ? diskId : partitionId,
            systemId: systemId,
          })
        );
        closeSidePanel();
      }}
      submitAppearance="positive"
      submitLabel="Create cache set"
    />
  );
};

export default CreateCacheSet;
