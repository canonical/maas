import { useSelector } from "react-redux";

import AllDropdown from "./AllDropdown";
import { generateSelectedAll } from "./utils";

import TableCheckbox from "@/app/machines/components/TableCheckbox";
import { Checked } from "@/app/machines/components/TableCheckbox/TableCheckbox";
import machineSelectors from "@/app/store/machine/selectors";
import type { FetchFilters } from "@/app/store/machine/types";

export enum Label {
  AllMachines = "All machines",
}

type Props = {
  callId?: string | null;
  filter: FetchFilters | null;
};

const AllCheckbox = ({ callId, filter }: Props): React.ReactElement => {
  const selected = useSelector(machineSelectors.selected);
  // A filter exists in the selected state when all machines in the current
  // table are selected.
  const allSelected = !!selected && "filter" in selected;
  const someSelected =
    !!selected &&
    (("items" in selected && !!selected.items?.length) ||
      ("groups" in selected && !!selected.groups?.length));

  return (
    <>
      <TableCheckbox
        aria-label={Label.AllMachines}
        // TODO: Remove the labelled-by attribute so that the aria-label is used.
        aria-labelledby=""
        callId={callId}
        isChecked={
          allSelected
            ? Checked.Checked
            : someSelected
              ? Checked.Mixed
              : Checked.Unchecked
        }
        onGenerateSelected={(checked) =>
          generateSelectedAll({ checked, filter })
        }
      />
      <AllDropdown callId={callId} filter={filter} />
    </>
  );
};

export default AllCheckbox;
