import type { ReactElement } from "react";

import { useDispatch } from "react-redux";

import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { machineActions } from "@/app/store/machine";
import type { Machine } from "@/app/store/machine/types";
import type { Partition } from "@/app/store/types/node";

type DeletePartitionProps = {
  systemId: Machine["system_id"];
  partitionId: Partition["id"];
};

const DeletePartition = ({
  systemId,
  partitionId,
}: DeletePartitionProps): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  return (
    <ModelActionForm
      aria-label="Delete partition"
      initialValues={{}}
      message={<>Are you sure you want to remove this partition?</>}
      modelType="partition"
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: `Delete partition`,
        category: "Machine storage",
        label: `Remove partition`,
      }}
      onSubmit={() => {
        dispatch(machineActions.cleanup());
        dispatch(
          machineActions.deletePartition({
            partitionId,
            systemId: systemId,
          })
        );
        closeSidePanel();
      }}
      submitAppearance="negative"
      submitLabel="Remove partition"
    />
  );
};

export default DeletePartition;
