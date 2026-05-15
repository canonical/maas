import type { Position } from "@canonical/react-components/dist/components/Tooltip/Tooltip";

import ScriptStatus from "@/app/base/components/ScriptStatus";
import { TestStatusStatus } from "@/app/store/types/node";

type Props = {
  children: React.ReactNode;
  status: TestStatusStatus;
  tooltipPosition?: Position;
};

const MachineTestStatus = ({
  children,
  status,
  tooltipPosition = "top-right",
}: Props): React.ReactElement => {
  switch (status) {
    case TestStatusStatus.PASSED:
      // We only want to show icons for tests that have not passed.
      return <>{children}</>;

    case TestStatusStatus.FAILED:
      return (
        <ScriptStatus
          status={status}
          tooltipMessage="Machine has failed tests."
          tooltipPosition={tooltipPosition}
        >
          {children}
        </ScriptStatus>
      );

    default:
      return <ScriptStatus status={status}>{children}</ScriptStatus>;
  }
};

export default MachineTestStatus;
