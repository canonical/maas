import { ContextualMenu, Icon } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import { generateSelectedAll, generateSelectedOnCurrentPage } from "../utils";

import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { FetchFilters } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  callId?: string | null;
  filter: FetchFilters | null;
};

export enum AllDropdownLabel {
  AllMachinesOptions = "All machines options",
  SelectAllMachines = "Select all machines",
  SelectAllMachinesOnThisPage = "Select all machines on this page",
}

const AllDropdown = ({ callId, filter }: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const selected = useSelector(machineSelectors.selected);
  const groups = useSelector((state: RootState) =>
    machineSelectors.listGroups(state, callId)
  );

  const selectAllMachines = () => {
    dispatch(
      machineActions.setSelected(generateSelectedAll({ checked: true, filter }))
    );
  };

  const selectMachinesOnCurrentPage = () => {
    dispatch(
      machineActions.setSelected(
        generateSelectedOnCurrentPage({ selected, groups })
      )
    );
  };

  return (
    <ContextualMenu
      links={[
        {
          children: AllDropdownLabel.SelectAllMachinesOnThisPage,
          onClick: selectMachinesOnCurrentPage,
        },
        {
          children: AllDropdownLabel.SelectAllMachines,
          onClick: selectAllMachines,
        },
      ]}
      position="left"
      toggleAppearance="base"
      toggleClassName="has-icon u-no-margin--bottom p-button--table-header select-all-dropdown "
      toggleLabel={<Icon name="chevron-down" />}
      toggleProps={{
        "aria-label": AllDropdownLabel.AllMachinesOptions,
      }}
    />
  );
};

export default AllDropdown;
