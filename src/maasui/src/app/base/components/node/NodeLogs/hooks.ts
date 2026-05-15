import { useEffect } from "react";

import { useDispatch, useSelector } from "react-redux";

import type { RootState } from "@/app/store/root/types";
import { scriptResultActions } from "@/app/store/scriptresult";
import scriptResultSelectors from "@/app/store/scriptresult/selectors";
import {
  ScriptResultDataType,
  ScriptResultNames,
  ScriptResultStatus,
} from "@/app/store/scriptresult/types";
import type {
  ScriptResult,
  ScriptResultData,
} from "@/app/store/scriptresult/types";
import type { Node } from "@/app/store/types/node";

/**
 * Fetch the installation log for a node.
 * @param systemId - The node id.
 * @returns The toggle callback.
 */
export const useGetInstallationOutput = (
  systemId: Node["system_id"]
): {
  log: ScriptResultData["combined"] | null;
  result: ScriptResult | null;
} => {
  const dispatch = useDispatch();
  const loading = useSelector((state: RootState) =>
    scriptResultSelectors.loading(state)
  );
  const scriptResults = useSelector((state: RootState) =>
    scriptResultSelectors.getByNodeId(state, systemId)
  );
  const installationResults = useSelector((state: RootState) =>
    scriptResultSelectors.getInstallationByNodeId(state, systemId)
  );
  const installationResult = (installationResults || []).find(
    ({ name }) => name === ScriptResultNames.INSTALL_LOG
  );
  const log = useSelector((state: RootState) =>
    scriptResultSelectors.getLogById(state, installationResult?.id)
  );

  useEffect(() => {
    // If the script results for this node haven't been loaded yet then
    // request them.
    if (!scriptResults?.length && !loading) {
      dispatch(scriptResultActions.getByNodeId(systemId));
    }
  }, [dispatch, scriptResults, loading, systemId]);

  useEffect(() => {
    if (
      !log &&
      installationResult &&
      [ScriptResultStatus.PASSED, ScriptResultStatus.FAILED].includes(
        installationResult?.status
      )
    ) {
      dispatch(
        scriptResultActions.getLogs(
          installationResult.id,
          ScriptResultDataType.COMBINED
        )
      );
    }
  }, [dispatch, installationResult, log, installationResults, scriptResults]);

  return { log: log?.combined || null, result: installationResult || null };
};
