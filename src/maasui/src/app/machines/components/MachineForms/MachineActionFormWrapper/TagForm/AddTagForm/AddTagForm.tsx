import NodeTagForm from "@/app/base/components/NodeTagForm";
import type { SelectedMachines } from "@/app/store/machine/types";
import { useFetchDeployedMachineCount } from "@/app/store/machine/utils/hooks";
import type { Tag } from "@/app/store/tag/types";

export type Props = {
  selectedMachines?: SelectedMachines | null;
  searchFilter?: string;
  name: string | null;
  onTagCreated: (tag: Tag) => void;
  isViewingDetails?: boolean;
  isViewingMachineConfig?: boolean;
  onCancel?: () => void;
};

export const AddTagForm = ({
  selectedMachines,
  name,
  onTagCreated,
  searchFilter,
  isViewingDetails,
  isViewingMachineConfig,
  onCancel,
}: Props): React.ReactElement => {
  let location = "list";
  if (isViewingMachineConfig) {
    location = "configuration";
  } else if (isViewingDetails) {
    location = "details";
  }

  const { machineCount: deployedSelectedMachineCount } =
    useFetchDeployedMachineCount({ selectedMachines, searchFilter });

  return (
    <NodeTagForm
      deployedMachinesCount={deployedSelectedMachineCount}
      generateDeployedMessage={(count: number) =>
        count === 1
          ? `${count} selected machine is deployed. The new kernel options will not be applied to this machine until it is redeployed.`
          : `${count} selected machines are deployed. The new kernel options will not be applied to these machines until they are redeployed.`
      }
      name={name}
      onCancel={onCancel}
      onSaveAnalytics={{
        action: "Manual tag created",
        category: `Machine ${location} create tag form`,
        label: "Save",
      }}
      onTagCreated={onTagCreated}
    />
  );
};

export default AddTagForm;
