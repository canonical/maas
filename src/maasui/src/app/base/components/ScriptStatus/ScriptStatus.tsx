import { Icon } from "@canonical/react-components";
import type { Position } from "@canonical/react-components/dist/components/Tooltip/Tooltip";
import classNames from "classnames";

import TooltipButton from "@/app/base/components/TooltipButton";
import { ScriptResultStatus } from "@/app/store/scriptresult/types";
import { TestStatusStatus } from "@/app/store/types/node";

type Props = {
  children?: React.ReactNode;
  status: ScriptResultStatus | TestStatusStatus;
  tooltipMessage?: React.ReactNode;
  tooltipPosition?: Position;
};

const getIconName = (status: ScriptResultStatus | TestStatusStatus): string => {
  switch (status) {
    case ScriptResultStatus.PENDING:
    case TestStatusStatus.PENDING:
      return "pending";
    case ScriptResultStatus.RUNNING:
    case ScriptResultStatus.APPLYING_NETCONF:
    case ScriptResultStatus.INSTALLING:
    case TestStatusStatus.RUNNING:
      return "running";
    case ScriptResultStatus.PASSED:
    case TestStatusStatus.PASSED:
      return "success";
    case ScriptResultStatus.FAILED:
    case ScriptResultStatus.ABORTED:
    case ScriptResultStatus.DEGRADED:
    case ScriptResultStatus.FAILED_APPLYING_NETCONF:
    case ScriptResultStatus.FAILED_INSTALLING:
    case TestStatusStatus.FAILED:
      return "error";
    case ScriptResultStatus.TIMEDOUT:
      return "timed-out";
    case ScriptResultStatus.SKIPPED:
      return "warning";
    case ScriptResultStatus.NONE:
    case TestStatusStatus.NONE:
      return "";
    default:
      return "";
  }
};

const ScriptStatus = ({
  children,
  status,
  tooltipMessage,
  tooltipPosition,
}: Props): React.ReactElement => {
  const iconName = getIconName(status);

  if (tooltipMessage) {
    return (
      <>
        <TooltipButton
          className={classNames({
            "u-nudge-left--x-small":
              children !== null && children !== undefined,
          })}
          iconName={iconName}
          message={tooltipMessage}
          position={tooltipPosition}
        />
        {children}
      </>
    );
  }

  return (
    <span>
      {iconName && (
        <Icon
          aria-label={iconName}
          className={classNames({
            "is-inline": children !== null && children !== undefined,
          })}
          name={iconName}
        />
      )}
      {children}
    </span>
  );
};

export default ScriptStatus;
