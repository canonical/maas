import { memo } from "react";

import { Tooltip } from "@canonical/react-components";
import { useSelector } from "react-redux";

import MachineTestStatus from "../MachineTestStatus";

import DoubleRow from "@/app/base/components/DoubleRow";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";

type Props = { systemId: Machine["system_id"] };

export const CoresColumn = ({ systemId }: Props): React.ReactElement | null => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );

  const formatShortArch = (arch: Machine["architecture"]) =>
    arch.includes("/generic") ? arch.split("/")[0] : arch;

  if (machine) {
    return (
      <DoubleRow
        className="u-align--right"
        primary={
          <MachineTestStatus
            data-testid="cores"
            status={machine.cpu_test_status.status}
            tooltipPosition="top-right"
          >
            {machine.cpu_count}
          </MachineTestStatus>
        }
        primaryAriaLabel="Cores"
        primaryClassName="u-align--right"
        secondary={
          <Tooltip message={machine.architecture} position="btm-left">
            <span data-testid="arch">
              {formatShortArch(machine.architecture)}
            </span>
          </Tooltip>
        }
        secondaryAriaLabel="Architecture"
      />
    );
  }
  return null;
};

export default memo(CoresColumn);
