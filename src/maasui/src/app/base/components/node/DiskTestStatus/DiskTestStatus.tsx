import { ScriptResultStatus } from "@/app/store/scriptresult/types";
import type { Disk } from "@/app/store/types/node";

type Props = { testStatus: Disk["test_status"] };

const DiskTestStatus = ({ testStatus }: Props): React.ReactElement => {
  switch (testStatus) {
    case ScriptResultStatus.PENDING:
      return <i aria-label="pending" className="p-icon--pending"></i>;
    case ScriptResultStatus.RUNNING:
    case ScriptResultStatus.APPLYING_NETCONF:
    case ScriptResultStatus.INSTALLING:
      return <i aria-label="running" className="p-icon--running"></i>;
    case ScriptResultStatus.PASSED:
      return (
        <>
          <i aria-label="ok" className="p-icon--success is-inline"></i>
          <span>OK</span>
        </>
      );
    case ScriptResultStatus.FAILED:
    case ScriptResultStatus.ABORTED:
    case ScriptResultStatus.DEGRADED:
    case ScriptResultStatus.FAILED_APPLYING_NETCONF:
    case ScriptResultStatus.FAILED_INSTALLING:
      return (
        <>
          <i aria-label="error" className="p-icon--error is-inline"></i>
          <span>Error</span>
        </>
      );
    case ScriptResultStatus.TIMEDOUT:
      return (
        <>
          <i aria-label="timed out" className="p-icon--timed-out is-inline"></i>
          <span>Timed out</span>
        </>
      );
    case ScriptResultStatus.SKIPPED:
      return (
        <>
          <i aria-label="skipped" className="p-icon--warning is-inline"></i>
          <span>Skipped</span>
        </>
      );
    default:
      return (
        <>
          <i
            aria-label="unknown"
            className="p-icon--power-unknown is-inline"
          ></i>
          <span>Unknown</span>
        </>
      );
  }
};

export default DiskTestStatus;
