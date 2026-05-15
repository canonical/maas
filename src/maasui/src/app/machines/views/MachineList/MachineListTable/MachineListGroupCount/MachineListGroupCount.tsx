import pluralize from "pluralize";

import Placeholder from "@/app/base/components/Placeholder/Placeholder";
import type {
  FetchFilters,
  MachineStateListGroup,
  FetchGroupKey,
} from "@/app/store/machine/types";
import { selectedToFilters } from "@/app/store/machine/utils";
import { useFetchMachineCount } from "@/app/store/machine/utils/hooks";

/**
 * Displays the aggregate count of machines in a specified machine list group
 * It optionally retrieves the count if it's not already known.
 */
const MachineListGroupCount = ({
  count,
  filter,
  group,
  grouping,
}: {
  count: number | null;
  filter: FetchFilters | null;
  group: MachineStateListGroup["value"];
  grouping: FetchGroupKey | null;
}): React.ReactElement => {
  const groupFilters = selectedToFilters({
    groups: [group],
    grouping,
  });

  const { machineCount, machineCountLoaded } = useFetchMachineCount(
    { ...filter, ...groupFilters },
    {
      isEnabled: count === null,
    }
  );

  if (count === null && !machineCountLoaded) {
    return <Placeholder>xx machines</Placeholder>;
  }

  return <span>{pluralize("machine", count || machineCount, true)}</span>;
};

export default MachineListGroupCount;
