import { memo } from "react";

import { useSelector } from "react-redux";

import MachineTestStatus from "../MachineTestStatus";

import DoubleRow from "@/app/base/components/DoubleRow";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";

type Props = { systemId: Machine["system_id"] };

export const DisksColumn = ({ systemId }: Props): React.ReactElement | null => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );

  if (machine) {
    return (
      <DoubleRow
        primary={
          <MachineTestStatus
            data-testid="disks"
            status={machine.storage_test_status.status}
            tooltipPosition="top-right"
          >
            {machine.physical_disk_count}
          </MachineTestStatus>
        }
        primaryClassName="u-align--right"
      />
    );
  }
  return null;
};

export default memo(DisksColumn);
