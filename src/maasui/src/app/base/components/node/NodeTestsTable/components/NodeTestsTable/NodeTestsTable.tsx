import { useEffect, useMemo, useState } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { Button } from "@canonical/react-components";
import type { SortingState } from "@tanstack/react-table";
import { useDispatch, useSelector } from "react-redux";

import type { Expanded } from "../useNodeTestsTableColumns/useNodeTestsTableColumns";
import useNodeTestsTableColumns, {
  ScriptResultAction,
} from "../useNodeTestsTableColumns/useNodeTestsTableColumns";

import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import { scriptResultActions } from "@/app/store/scriptresult";
import scriptResultSelectors from "@/app/store/scriptresult/selectors";
import type {
  PartialScriptResult,
  ScriptResult,
} from "@/app/store/scriptresult/types";

type Props = {
  node: ControllerDetails | MachineDetails;
  isLoading?: boolean;
  scriptResults: ScriptResult[];
};

export type NodeTestRow = ScriptResult & {
  history?: NodeTestRow[];
  isHistory?: boolean;
  hasMetrics?: boolean;
};

const getNodeTestsTableData = (
  data: ScriptResult[],
  history: Record<number, PartialScriptResult[]>,
  expanded: Expanded | null
) => {
  const newData: NodeTestRow[] = [];
  data.forEach((scriptResult) => {
    if (history[scriptResult.id] && scriptResult.id === expanded?.id) {
      newData.push({
        ...scriptResult,
        history: history[scriptResult.id]
          .filter((historyItem) => historyItem.id !== scriptResult.id)
          .map((historyItem) => {
            return {
              ...scriptResult,
              ...historyItem,
              isHistory: true,
            };
          }),
        hasMetrics: scriptResult.results.length > 0,
      });
    } else {
      newData.push({
        ...scriptResult,
        hasMetrics: scriptResult.results.length > 0,
      });
    }
  });
  return newData;
};

const useScriptResultHistory = (scriptResults: ScriptResult[]) => {
  const history = useSelector(scriptResultSelectors.history);
  const dispatch = useDispatch();

  useEffect(() => {
    scriptResults.forEach((scriptResult) => {
      if (history[scriptResult.id] && history[scriptResult.id].length === 0) {
        dispatch(scriptResultActions.getHistory(scriptResult.id));
      }
    });
  }, [dispatch, history, scriptResults]);

  return history;
};

const NodeTestsTable = ({ isLoading, node, scriptResults }: Props) => {
  const [expanded, setExpanded] = useState<Expanded | null>(null);
  const columns = useNodeTestsTableColumns({
    node,
    scriptResults,
    expanded,
    setExpanded,
  });
  const [sorting, setSorting] = useState<SortingState>([
    { id: "name", desc: true },
  ]);
  const history = useScriptResultHistory(scriptResults);
  const data = useMemo(() => {
    return getNodeTestsTableData(scriptResults, history, expanded);
  }, [scriptResults, history, expanded]);

  return (
    <>
      <GenericTable
        aria-label="Test results"
        className="node-tests-table p-table-expanding--light"
        columns={columns}
        data={data}
        getSubRows={(originalRow) => originalRow.history}
        isLoading={isLoading || false}
        noData="No results available."
        setSorting={setSorting}
        sorting={sorting}
        variant="regular"
      />
      <div className="u-align--right u-nudge-left--small">
        {expanded?.content === ScriptResultAction.VIEW_PREVIOUS_TESTS ? (
          <>
            {!history || history[expanded?.id]?.length <= 1 ? (
              <p
                className="u-align--center u-no-max-width"
                data-testid="no-history"
              >
                {history[expanded?.id]?.length === 1 ? (
                  "This test has only been run once."
                ) : (
                  <></>
                )}
              </p>
            ) : null}
            <Button
              className="u-no-margin--bottom"
              onClick={() => {
                setExpanded(null);
              }}
            >
              Close
            </Button>
          </>
        ) : null}
      </div>
    </>
  );
};

export default NodeTestsTable;
