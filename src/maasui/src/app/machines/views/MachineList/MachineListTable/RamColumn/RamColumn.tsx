import { memo } from "react";

import { useSelector } from "react-redux";

import MachineTestStatus from "../MachineTestStatus";

import DoubleRow from "@/app/base/components/DoubleRow";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";

type Props = { systemId: Machine["system_id"] };

export const RamColumn = ({ systemId }: Props): React.ReactElement | null => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );

  if (machine) {
    return (
      <DoubleRow
        primary={
          <MachineTestStatus
            status={machine.memory_test_status.status}
            tooltipPosition="top-right"
          >
            <span data-testid="memory">{machine.memory}</span>&nbsp;
            <small className="u-text--light">GiB</small>
          </MachineTestStatus>
        }
        primaryClassName="u-align--right"
      />
    );
  }
  return null;
};

export default memo(RamColumn);
