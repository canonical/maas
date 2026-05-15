import cloneDeep from "clone-deep";
import { useSelector } from "react-redux";

import TableCheckbox from "@/app/machines/components/TableCheckbox";
import { Checked } from "@/app/machines/components/TableCheckbox/TableCheckbox";
import machineSelectors from "@/app/store/machine/selectors";
import type {
  MachineStateListGroup,
  FetchGroupKey,
} from "@/app/store/machine/types";

type Props = {
  callId?: string | null;
  group: MachineStateListGroup | null;
  grouping: FetchGroupKey | null;
  groupName: MachineStateListGroup["name"];
};

const GroupCheckbox = ({
  callId,
  group,
  grouping,
  groupName,
}: Props): React.ReactElement | null => {
  const selected = useSelector(machineSelectors.selected);
  const allSelected = !!selected && "filter" in selected;
  if (!group) {
    return null;
  }
  // Whether this group is currently selected.
  const groupSelected =
    !!selected &&
    "items" in selected &&
    group.items.every((item) => selected.items?.includes(item));
  // Whether some of the machines in the group are selected.
  const childrenSelected =
    !!selected &&
    "items" in selected &&
    !!selected.items?.find((selectedId) => group?.items.includes(selectedId));

  return (
    <TableCheckbox
      callId={callId}
      extraClasses="u-align-header-checkbox"
      inputLabel={<strong>{groupName}</strong>}
      isChecked={
        allSelected || groupSelected
          ? Checked.Checked
          : childrenSelected
            ? Checked.Mixed
            : Checked.Unchecked
      }
      isDisabled={group?.count === 0 || allSelected}
      onGenerateSelected={(checked) => {
        const newSelected =
          !selected || "filter" in selected
            ? { items: [] }
            : cloneDeep(selected);
        newSelected.items = newSelected.items ?? [];

        if (
          checked &&
          !group.items.every((item) => newSelected.items?.includes(item))
        ) {
          // If the checkbox has been checked and the group's visible items are not
          // in the list, add them.
          newSelected.items = newSelected.items.concat(group.items);
          newSelected.grouping = grouping;
        } else if (
          !checked &&
          group.items.some((item) => newSelected.items?.includes(item))
        ) {
          // If the checkbox has been unchecked and the group's visible items are
          // in the list then remove them.
          newSelected.items = newSelected.items.filter(
            (selectedItem) => !group.items.includes(selectedItem)
          );
        }

        return newSelected;
      }}
    />
  );
};

export default GroupCheckbox;
