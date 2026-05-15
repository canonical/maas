import type { ReactElement } from "react";

import { ContextualMenu } from "@canonical/react-components";

import { useSidePanel } from "@/app/base/side-panel-context";
import AddChassisForm from "@/app/machines/components/MachineForms/AddChassis/AddChassisForm";
import AddMachineForm from "@/app/machines/components/MachineForms/AddMachine/AddMachineForm";

type AddHardwareMenuProps = {
  disabled?: boolean;
};

export const AddHardwareMenu = ({
  disabled = false,
}: AddHardwareMenuProps): ReactElement => {
  const { openSidePanel } = useSidePanel();
  return (
    <ContextualMenu
      className="is-maas-select"
      data-testid="add-hardware-dropdown"
      hasToggleIcon
      links={[
        {
          children: "Machine",
          onClick: () => {
            openSidePanel({
              component: AddMachineForm,
              title: "Add machine",
            });
          },
        },
        {
          children: "Chassis",
          onClick: () => {
            openSidePanel({
              component: AddChassisForm,
              title: "Add chassis",
            });
          },
        },
      ]}
      position="right"
      toggleDisabled={disabled}
      toggleLabel="Add hardware"
    />
  );
};

export default AddHardwareMenu;
