import type { ReactElement } from "react";

import { useDispatch } from "react-redux";

import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { machineActions } from "@/app/store/machine";
import type { Machine } from "@/app/store/machine/types";
import type { Disk } from "@/app/store/types/node";

type SetBootDiskProps = {
  systemId: Machine["system_id"];
  diskId: Disk["id"];
};

const SetBootDisk = ({ systemId, diskId }: SetBootDiskProps): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  return (
    <ModelActionForm
      aria-label="Set boot disk"
      initialValues={{}}
      message={<>Are you sure you want to set boot disk?</>}
      modelType="boot disk"
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Set boot disk",
        category: "Machine storage",
        label: "Set boot disk",
      }}
      onSubmit={() => {
        dispatch(machineActions.cleanup());
        dispatch(
          machineActions.setBootDisk({
            blockId: diskId,
            systemId: systemId,
          })
        );
        closeSidePanel();
      }}
      submitAppearance="positive"
      submitLabel="Set boot disk"
    />
  );
};

export default SetBootDisk;
