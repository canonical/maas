import type { ReactElement } from "react";

import { Button } from "@canonical/react-components";

import DoubleRow from "@/app/base/components/DoubleRow";
import GroupCheckbox from "@/app/machines/views/MachineList/MachineListTable/GroupCheckbox";
import MachineListGroupCount from "@/app/machines/views/MachineList/MachineListTable/MachineListGroupCount";
import type { GroupRowsProps } from "@/app/machines/views/MachineList/MachineListTable/types";
import type { MachineStateListGroup } from "@/app/store/machine/types";

export enum Label {
  HideGroup = "Hide",
  ShowGroup = "Show",
}

const GroupColumn = ({
  group,
  hiddenGroups,
  setHiddenGroups,
  showActions,
  callId,
  grouping,
  filter,
}: Pick<
  GroupRowsProps,
  "callId" | "filter" | "hiddenGroups" | "setHiddenGroups" | "showActions"
> & {
  grouping: NonNullable<GroupRowsProps["grouping"]>;
  group: MachineStateListGroup;
}): ReactElement => {
  const { collapsed, count, name, value } = group;
  return (
    <>
      <DoubleRow
        data-testid="group-cell"
        primary={
          showActions ? (
            <GroupCheckbox
              callId={callId}
              group={group}
              groupName={name}
              grouping={grouping}
            />
          ) : (
            <strong>{name}</strong>
          )
        }
        secondary={
          <MachineListGroupCount
            count={count}
            filter={filter}
            group={value}
            grouping={grouping}
          />
        }
        secondaryClassName={
          showActions ? "u-nudge--secondary-row u-align--left" : null
        }
      />
      <div className="machine-list__group-toggle">
        <Button
          appearance="base"
          dense
          hasIcon
          onClick={() => {
            if (collapsed) {
              setHiddenGroups &&
                setHiddenGroups(
                  hiddenGroups.filter((hiddenGroup) => hiddenGroup !== value)
                );
            } else {
              setHiddenGroups &&
                setHiddenGroups(hiddenGroups.concat([value as string]));
            }
          }}
        >
          {collapsed ? (
            <i className="p-icon--plus">{Label.ShowGroup}</i>
          ) : (
            <i className="p-icon--minus">{Label.HideGroup}</i>
          )}
        </Button>
      </div>
    </>
  );
};

export default GroupColumn;
