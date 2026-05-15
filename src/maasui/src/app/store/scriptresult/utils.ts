import type { ScriptResult } from "./types";
import { ScriptResultStatus, ScriptResultType } from "./types";

/**
 * Determine whether a script's result status should be considered "failed".
 * @param status - The script result's status.
 * @returns Whether the script result should be considered "failed".
 */
export const scriptResultFailed = (status: ScriptResultStatus): boolean =>
  [
    ScriptResultStatus.DEGRADED,
    ScriptResultStatus.FAILED_APPLYING_NETCONF,
    ScriptResultStatus.FAILED_INSTALLING,
    ScriptResultStatus.FAILED,
    ScriptResultStatus.TIMEDOUT,
  ].includes(status);

/**
 * Determine whether a script's result status should be considered "in progress".
 * @param status - The script result's status.
 * @returns Whether the script result should be considered "in progress".
 */
export const scriptResultInProgress = (status: ScriptResultStatus): boolean =>
  [
    ScriptResultStatus.APPLYING_NETCONF,
    ScriptResultStatus.INSTALLING,
    ScriptResultStatus.PENDING,
    ScriptResultStatus.RUNNING,
  ].includes(status);

/**
 * Check whether a script result can be suppressed.
 * @param result - A script result.
 * @returns Whether the script result can be suppressed.
 */
export const canBeSuppressed = (scriptResult: ScriptResult): boolean =>
  scriptResult.result_type === ScriptResultType.TESTING &&
  scriptResultFailed(scriptResult.status);
