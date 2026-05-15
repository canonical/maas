import { createSelector } from "@reduxjs/toolkit";

import nodeScriptResultSelectors from "../nodescriptresult/selectors";
import type { Node } from "../types/node";

import type {
  PartialScriptResult,
  ScriptResult,
  ScriptResultData,
} from "./types";
import { ScriptResultType } from "./types";
import { scriptResultFailed } from "./utils";

import { HardwareType } from "@/app/base/enum";
import type { APIError } from "@/app/base/types";
import type { NodeScriptResultState } from "@/app/store/nodescriptresult/types";
import type { RootState } from "@/app/store/root/types";

/**
 * Returns list of all script results.
 * @param {RootState} state - Redux state
 * @returns List of script results
 */
const all = (state: RootState): ScriptResult[] => state.scriptresult.items;

/**
 * Returns script result history
 * @param {RootState} state - Redux state
 * @returns script history
 */
const history = (
  state: RootState
): Record<ScriptResult["id"], PartialScriptResult[]> =>
  state.scriptresult.history;

/**
 * Returns script result logs
 * @param {RootState} state - Redux state
 * @returns script logs
 */
const logs = (
  state: RootState
): Record<ScriptResult["id"], ScriptResultData> | null =>
  state.scriptresult.logs;

/**
 * Returns true if script results are loading
 * @param {RootState} state - Redux state
 * @returns {ScriptResultState["loading"]} Scripts results are loading
 */

const loading = (state: RootState): boolean => state.scriptresult.loading;

/**
 * Returns true if script results have loaded
 * @param {RootState} state - Redux state
 * @returns {ScriptResultState["loaded"]} Scripts results have loaded
 */
const loaded = (state: RootState): boolean => state.scriptresult.loaded;

/**
 * Returns true if script results have saved
 * @param {RootState} state - Redux state
 * @returns {ScriptResultState["saved"]} Scripts results have saved
 */
const saved = (state: RootState): boolean => state.scriptresult.saved;

/**
 * Returns script result errors.
 * @param {RootState} state - The redux state.
 * @returns {ScriptResultState["errors"]} Errors for a script result.
 */
const errors = (state: RootState): APIError => state.scriptresult.errors;

/**
 * Get a script result by id.
 * @param state - The redux state.
 * @param id - A script result id.
 * @returns A script result.
 */
const getById = createSelector(
  [all, (_state: RootState, id: ScriptResult["id"] | null | undefined) => id],
  (items, id) => {
    if (!id && id !== 0) {
      return null;
    }
    return items.find((item) => item.id === id) || null;
  }
);

/**
 * Returns true if script results have errors
 * @param {RootState} state - Redux state
 * @returns {Boolean} Script results have errors
 */
const hasErrors = createSelector([errors], (errors) =>
  errors && typeof errors === "object"
    ? Object.entries(errors).length > 0
    : !!errors
);

const getResult = (
  nodeScriptResult: NodeScriptResultState["items"],
  scriptResults: ScriptResult[],
  nodeId: Node["system_id"] | null | undefined,
  resultTypes?: ScriptResult["result_type"][] | null,
  hardwareTypes?: ScriptResult["hardware_type"][] | null
): ScriptResult[] | null => {
  if (!nodeId) {
    return null;
  }
  const nodeResultIds =
    nodeId in nodeScriptResult ? nodeScriptResult[nodeId] : [];
  if (!nodeResultIds.length) {
    return null;
  }
  return scriptResults.filter((scriptResult) => {
    const matchesId = nodeResultIds.includes(scriptResult.id);
    const matchesResult = resultTypes?.length
      ? resultTypes.includes(scriptResult.result_type)
      : true;
    const matchesHardware = hardwareTypes?.length
      ? hardwareTypes.includes(scriptResult.hardware_type)
      : true;
    return matchesId && matchesResult && matchesHardware;
  });
};

const getFailed = (results: ScriptResult[] | null): ScriptResult[] | null => {
  if (results) {
    // Filter for only the failed results.
    return results.filter(({ status }) => scriptResultFailed(status));
  }
  return results;
};

/**
 * Returns script results by node id
 * @param state - Redux state
 * @returns script results
 */
const getByNodeId = createSelector(
  [
    nodeScriptResultSelectors.all,
    all,
    (_: RootState, nodeId: Node["system_id"] | null | undefined) => nodeId,
  ],
  (nodeScriptResult, scriptResults, nodeId): ScriptResult[] | null =>
    getResult(nodeScriptResult, scriptResults, nodeId)
);

/**
 * Returns hardware testing results (CPU, Memory, Network) by node id
 * @param state - Redux state
 * @param nodeId - node system id
 * @param failed - Whether to filter by the failed results.
 * @returns script results
 */
const getHardwareTestingByNodeId = createSelector(
  [
    nodeScriptResultSelectors.all,
    all,
    (
      _: RootState,
      nodeId: Node["system_id"] | null | undefined,
      failed?: boolean
    ) => ({
      failed,
      nodeId,
    }),
  ],
  (nodeScriptResult, scriptResults, { failed, nodeId }) => {
    const results = getResult(
      nodeScriptResult,
      scriptResults,
      nodeId,
      [ScriptResultType.TESTING],
      [HardwareType.CPU, HardwareType.Memory, HardwareType.Network]
    );
    if (failed) {
      return getFailed(results);
    }
    return results;
  }
);

/**
 * Returns deployment script results by node id
 * @param state - Redux state
 * @param nodeId - node system id
 * @param failed - Whether to filter by the failed results.
 * @returns script results
 */
const getDeploymentByNodeId = createSelector(
  [
    nodeScriptResultSelectors.all,
    all,
    (
      _: RootState,
      nodeId: Node["system_id"] | null | undefined,
      failed?: boolean
    ) => ({
      failed,
      nodeId,
    }),
  ],
  (nodeScriptResult, scriptResults, { failed, nodeId }) => {
    const results = getResult(nodeScriptResult, scriptResults, nodeId, [
      ScriptResultType.DEPLOYMENT,
    ]);
    if (failed) {
      return getFailed(results);
    }
    return results;
  }
);

/**
 * Returns commissioning testing results (CPU, Memory, Network) by node id
 * @param state - Redux state
 * @param nodeId - node system id
 * @param failed - Whether to filter by the failed results.
 * @returns script results
 */
const getCommissioningByNodeId = createSelector(
  [
    nodeScriptResultSelectors.all,
    all,
    (
      _: RootState,
      nodeId: Node["system_id"] | null | undefined,
      failed?: boolean
    ) => ({
      failed,
      nodeId,
    }),
  ],
  (nodeScriptResult, scriptResults, { failed, nodeId }) => {
    const results = getResult(
      nodeScriptResult,
      scriptResults,
      nodeId,
      [ScriptResultType.COMMISSIONING],
      [HardwareType.Node]
    );
    if (failed) {
      return getFailed(results);
    }
    return results;
  }
);

/**
 * Returns network testing results by node id.
 * @param state - Redux state.
 * @param nodeId - Node system id.
 * @param failed - Whether to filter by the failed results.
 * @returns Network testing script results.
 */
const getNetworkTestingByNodeId = createSelector(
  [
    nodeScriptResultSelectors.all,
    all,
    (
      _: RootState,
      nodeId: Node["system_id"] | null | undefined,
      failed?: boolean
    ) => ({
      failed,
      nodeId,
    }),
  ],
  (nodeScriptResult, scriptResults, { failed, nodeId }) => {
    const results = getResult(
      nodeScriptResult,
      scriptResults,
      nodeId,
      [ScriptResultType.TESTING],
      [HardwareType.Network]
    );
    if (failed) {
      return getFailed(results);
    }
    return results;
  }
);

/**
 * Returns storage testing results by node id
 * @param state - Redux state
 * @param nodeId - node system id
 * @param failed - Whether to filter by the failed results.
 * @returns script results
 */
const getStorageTestingByNodeId = createSelector(
  [
    nodeScriptResultSelectors.all,
    all,
    (
      _: RootState,
      nodeId: Node["system_id"] | null | undefined,
      failed?: boolean
    ) => ({
      failed,
      nodeId,
    }),
  ],
  (nodeScriptResult, scriptResults, { failed, nodeId }) => {
    const results = getResult(
      nodeScriptResult,
      scriptResults,
      nodeId,
      [ScriptResultType.TESTING],
      [HardwareType.Storage]
    );
    if (failed) {
      return getFailed(results);
    }
    return results;
  }
);

/**
 * Returns other testing results by node id
 * @param state - Redux state
 * @param nodeId - node system id
 * @param failed - Whether to filter by the failed results.
 * @returns script results
 */
const getOtherTestingByNodeId = createSelector(
  [
    nodeScriptResultSelectors.all,
    all,
    (
      _: RootState,
      nodeId: Node["system_id"] | null | undefined,
      failed?: boolean
    ) => ({
      failed,
      nodeId,
    }),
  ],
  (nodeScriptResult, scriptResults, { failed, nodeId }) => {
    const results = getResult(
      nodeScriptResult,
      scriptResults,
      nodeId,
      [ScriptResultType.TESTING],
      [HardwareType.Node]
    );
    if (failed) {
      return getFailed(results);
    }
    return results;
  }
);

type NodeScriptResults = Record<string, ScriptResult[]>;

/**
 * Returns the failed testing script results for each of the supplied node ids.
 * @param state - Redux state.
 * @returns Failed testing script results for each node.
 */
const getFailedTestingResultsByNodeIds = createSelector(
  [
    nodeScriptResultSelectors.all,
    all,
    (_: RootState, nodeId: Node["system_id"][]) => nodeId,
  ],
  (nodeScriptResult, scriptResults, nodeIds): NodeScriptResults =>
    (nodeIds || []).reduce<NodeScriptResults>((grouped, nodeId) => {
      let results = getResult(nodeScriptResult, scriptResults, nodeId, [
        ScriptResultType.TESTING,
      ]);
      results = getFailed(results);
      if (results) {
        grouped[nodeId] = results;
      }
      return grouped;
    }, {})
);

/**
 * Returns installation results by node id.
 * @param state - Redux state.
 * @param nodeId - node system id.
 * @param failed - Whether to filter by the failed results.
 * @returns installation script results.
 */
const getInstallationByNodeId = createSelector(
  [
    nodeScriptResultSelectors.all,
    all,
    (
      _: RootState,
      nodeId: Node["system_id"] | null | undefined,
      failed?: boolean
    ) => ({
      failed,
      nodeId,
    }),
  ],
  (nodeScriptResult, scriptResults, { failed, nodeId }) => {
    const results = getResult(nodeScriptResult, scriptResults, nodeId, [
      ScriptResultType.INSTALLATION,
    ]);
    if (failed) {
      return getFailed(results);
    }
    return results;
  }
);

/**
 * Returns installation results by node id.
 * @param state - Redux state.
 * @param nodeId - node system id.
 * @param failed - Whether to filter by the failed results.
 * @returns installation script results.
 */
const getInstallationLogsByNodeId = createSelector(
  [
    nodeScriptResultSelectors.all,
    all,
    logs,
    (_: RootState, nodeId: Node["system_id"] | null | undefined) => nodeId,
  ],
  (nodeScriptResult, scriptResults, logs, nodeId) => {
    const results = getResult(nodeScriptResult, scriptResults, nodeId, [
      ScriptResultType.INSTALLATION,
    ]);
    if (!results) {
      return null;
    }
    return results.reduce<ScriptResultData[]>((resultData, result) => {
      if (logs && result && logs[result.id]) {
        resultData.push(logs[result.id]);
      }
      return resultData;
    }, []);
  }
);

const getHistoryById = createSelector(
  [
    history,
    (_: RootState, scriptResultId: ScriptResult["id"]) => scriptResultId,
  ],
  (history, scriptResultId) => {
    if (scriptResultId in history) {
      return history[scriptResultId];
    }
    return null;
  }
);

const getHistoryByAllIds = createSelector(
  [
    history,
    (_: RootState, scriptResultIds: ScriptResult["id"][]) => scriptResultIds,
  ],
  (history, scriptResultIds) => {
    return scriptResultIds
      .filter((id) => id in history)
      .map((id) => history[id]);
  }
);

const getLogById = createSelector(
  [
    logs,
    (_: RootState, scriptResultId: ScriptResult["id"] | null | undefined) =>
      scriptResultId,
  ],
  (logs, scriptResultId) => {
    return scriptResultId && logs && scriptResultId in logs
      ? logs[scriptResultId]
      : null;
  }
);

const scriptResult = {
  all,
  errors,
  getById,
  getByNodeId,
  getCommissioningByNodeId,
  getDeploymentByNodeId,
  getFailedTestingResultsByNodeIds,
  getHardwareTestingByNodeId,
  getHistoryById,
  getHistoryByAllIds,
  getInstallationByNodeId,
  getInstallationLogsByNodeId,
  getLogById,
  getNetworkTestingByNodeId,
  getOtherTestingByNodeId,
  getStorageTestingByNodeId,
  hasErrors,
  history,
  loaded,
  loading,
  logs,
  saved,
};

export default scriptResult;
