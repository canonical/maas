import type { ReactNode } from "react";

import cloneDeep from "clone-deep";
import { useSelector } from "react-redux";

import TableCheckbox from "@/app/machines/components/TableCheckbox";
import { Checked } from "@/app/machines/components/TableCheckbox/TableCheckbox";
import machineSelectors from "@/app/store/machine/selectors";
import type {
  FetchGroupKey,
  FilterGroupOptionType,
  Machine,
  MachineMeta,
  MachineStateListGroup,
  SelectedMachines,
} from "@/app/store/machine/types";

type Props = {
  callId?: string | null;
  label: ReactNode;
  groupValue?: MachineStateListGroup["value"];
  systemId: Machine[MachineMeta.PK];
  machines?: Machine[];
};

export const getSelectedMachinesRange = ({
  systemId,
  machines,
  selected,
}: {
  systemId: string;
  machines: Machine[];
  selected: SelectedMachines | null;
}): {
  items?: string[] | undefined;
  groups?: (FilterGroupOptionType | null)[] | undefined;
  grouping?: FetchGroupKey | null | undefined;
} => {
  const newSelected =
    !selected || "filter" in selected ? { items: [] } : cloneDeep(selected);
  newSelected.items = newSelected.items ?? [];

  const previousChecked = newSelected.items.at(-1);
  if (!previousChecked) {
    // if there's no previous selected item, select the clicked item
    newSelected.items.push(systemId);
    return newSelected;
  }
  const currentIndex = machines.findIndex(
    (machine) => machine.system_id === systemId
  );
  const previousIndex = machines.findIndex(
    (machine) => machine.system_id === previousChecked
  );

  // Get the start and end points of the selected range
  const startIndex = Math.min(currentIndex, previousIndex);
  const endIndex = Math.max(currentIndex, previousIndex);

  // Check if the resulting indexes make a valid range for selection
  if (startIndex > -1 && endIndex > -1) {
    // loop through the machine list, add the ids that have not been added already
    for (let i = startIndex; i <= endIndex; i++) {
      if (!newSelected.items.includes(machines[i].system_id)) {
        newSelected.items.push(machines[i].system_id);
      }
    }
  }

  return newSelected;
};

const MachineCheckbox = ({
  callId,
  label,
  groupValue,
  systemId,
  machines,
}: Props): React.ReactElement => {
  const selected = useSelector(machineSelectors.selected);
  const allSelected = !!selected && "filter" in selected;
  // Whether the group this machine appears in is selected.
  const groupSelected =
    typeof groupValue !== "undefined" &&
    groupValue !== null &&
    !!selected &&
    "groups" in selected &&
    selected.groups?.includes(groupValue);
  // Display this machine as checked if it or the machine's group or all
  // machines are selected.
  const isChecked =
    allSelected ||
    groupSelected ||
    (!!selected && "items" in selected && !!selected.items?.includes(systemId));

  return (
    <TableCheckbox
      callId={callId}
      inputLabel={label}
      isChecked={isChecked ? Checked.Checked : Checked.Unchecked}
      isDisabled={allSelected || groupSelected}
      onGenerateSelected={(checked, isRange) => {
        if (checked && isRange && !groupValue) {
          return getSelectedMachinesRange({
            systemId,
            machines: machines ?? [],
            selected,
          });
        }

        const newSelected =
          !selected || "filter" in selected
            ? { items: [] }
            : cloneDeep(selected);
        newSelected.items = newSelected.items ?? [];
        if (checked && !newSelected.items?.includes(systemId)) {
          // If the checkbox has been checked and the system ID is not in the list
          // then add it.
          newSelected.items.push(systemId);
        } else if (!checked && newSelected.items?.includes(systemId)) {
          // If the checkbox has been unchecked and the system ID is in the list
          // then remove it.
          newSelected.items = newSelected.items.filter(
            (selectedId) => selectedId !== systemId
          );
        }
        return newSelected;
      }}
    />
  );
};

export default MachineCheckbox;
