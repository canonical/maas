import {
  Notification as NotificationBanner,
  Button,
} from "@canonical/react-components";
import pluralize from "pluralize";
import { useDispatch } from "react-redux";

import { machineActions } from "@/app/store/machine";
import { FilterMachines } from "@/app/store/machine/utils";

type Props = {
  filter: string;
  machineCount: number | null;
  selectedCount: number;
};

export const MachineListSelectedCount = ({
  filter,
  machineCount,
  selectedCount,
}: Props): React.ReactElement => {
  const dispatch = useDispatch();

  return (
    <NotificationBanner
      borderless
      className="u-no-margin--bottom"
      title="Selection"
    >
      {machineCount && selectedCount < machineCount ? (
        <>
          {selectedCount} {pluralize("machine", selectedCount)} selected.{" "}
          <Button
            appearance="link"
            onClick={() => {
              dispatch(
                machineActions.setSelected({
                  filter: FilterMachines.parseFetchFilters(filter),
                })
              );
            }}
          >
            {filter
              ? `Select all ${machineCount} filtered machines`
              : `Select all ${machineCount} machines`}
          </Button>
        </>
      ) : (
        <>
          Selected all {machineCount}
          {filter ? " filtered" : ""} machines.{" "}
          <Button
            appearance="link"
            onClick={() => {
              dispatch(machineActions.setSelected(null));
            }}
          >
            Clear selection
          </Button>
        </>
      )}
    </NotificationBanner>
  );
};

export default MachineListSelectedCount;
