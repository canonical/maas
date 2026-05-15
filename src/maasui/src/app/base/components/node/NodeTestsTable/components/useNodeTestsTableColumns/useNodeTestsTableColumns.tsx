import type { Dispatch } from "react";
import { useMemo } from "react";

import { Icon, Input, Tooltip } from "@canonical/react-components";
import type { ColumnDef, Row } from "@tanstack/react-table";
import { useDispatch } from "react-redux";
import { Link } from "react-router";

import ScriptRunTime from "../../ScriptRunTime";
import type { NodeTestRow } from "../NodeTestsTable/NodeTestsTable";

import ScriptStatus from "@/app/base/components/ScriptStatus";
import { useSendAnalytics } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import type { ControllerDetails } from "@/app/store/controller/types";
import { machineActions } from "@/app/store/machine";
import type { MachineDetails } from "@/app/store/machine/types";
import type { ScriptResult } from "@/app/store/scriptresult/types";
import { ScriptResultType } from "@/app/store/scriptresult/types";
import { canBeSuppressed } from "@/app/store/scriptresult/utils";
import { nodeIsMachine } from "@/app/store/utils";
import { formatUtcDatetime } from "@/app/utils/time";

type Props = {
  node: ControllerDetails | MachineDetails;
  scriptResults: ScriptResult[];
  expanded: Expanded | null;
  setExpanded: Dispatch<React.SetStateAction<Expanded | null>>;
};
export enum ScriptResultAction {
  VIEW_METRICS = "viewMetrics",
  VIEW_PREVIOUS_TESTS = "viewPreviousTests",
}

export type Expanded = {
  id: ScriptResult["id"];
  content: ScriptResultAction;
};

export type SetExpanded = (expanded: Expanded) => void;

type NodeTestsTableColumnDef = ColumnDef<NodeTestRow, Partial<NodeTestRow>>;

const useNodeTestsTableColumns = ({
  node,
  scriptResults,
  expanded,
  setExpanded,
}: Props): NodeTestsTableColumnDef[] => {
  const dispatch = useDispatch();
  const sendAnalytics = useSendAnalytics();

  const containsTesting = scriptResults.some(
    (result) => result.result_type === ScriptResultType.TESTING
  );
  const isMachine = nodeIsMachine(node);
  const showSuppressCol = containsTesting && isMachine;

  return useMemo(
    () => [
      ...(showSuppressCol
        ? [
            {
              id: "suppress-col",
              header: "Suppress",
              accessorKey: "suppress-col",
              enableSorting: false,
              cell: ({ row }: { row: Row<NodeTestRow> }) => {
                if (!row.original.isHistory) {
                  const isSuppressible = canBeSuppressed(row.original);
                  return (
                    <Tooltip
                      data-testid="suppress-tooltip"
                      message={
                        isSuppressible
                          ? null
                          : "Only failed testing scripts can be suppressed."
                      }
                    >
                      <Input
                        checked={row.original.suppressed}
                        data-testid="suppress-script-results"
                        disabled={!isSuppressible}
                        id={`suppress-${row.original.id}`}
                        label=" "
                        labelClassName="p-checkbox--inline u-no-padding--left"
                        onChange={() => {
                          if (showSuppressCol) {
                            if (row.original.suppressed) {
                              dispatch(
                                machineActions.unsuppressScriptResults(
                                  node.system_id,
                                  [row.original]
                                )
                              );
                              sendAnalytics(
                                "Machine testing",
                                "Unsuppress script result failure",
                                "Unsuppress"
                              );
                            } else {
                              dispatch(
                                machineActions.suppressScriptResults(
                                  node.system_id,
                                  [row.original]
                                )
                              );
                              sendAnalytics(
                                "Machine testing",
                                "Suppress script result failure",
                                "Suppress"
                              );
                            }
                          }
                        }}
                        type="checkbox"
                      />
                    </Tooltip>
                  );
                } else {
                  return null;
                }
              },
            },
          ]
        : []),
      {
        id: "name",
        header: "Name",
        accessorKey: "name",
        enableSorting: false,
        cell: ({ row }) =>
          !row.original.isHistory ? (
            <Link
              data-testid="details-link"
              to={
                isMachine
                  ? row.original.result_type === ScriptResultType.COMMISSIONING
                    ? urls.machines.machine.scriptsResults.commissioning.scriptResult(
                        {
                          id: node.system_id,

                          scriptResultId: row.original.id,
                        }
                      )
                    : row.original.result_type === ScriptResultType.DEPLOYMENT
                      ? urls.machines.machine.scriptsResults.deployment.scriptResult(
                          {
                            id: node.system_id,
                            scriptResultId: row.original.id,
                          }
                        )
                      : urls.machines.machine.scriptsResults.testing.scriptResult(
                          {
                            id: node.system_id,
                            scriptResultId: row.original.id,
                          }
                        )
                  : urls.controllers.controller.commissioning.scriptResult({
                      id: node.system_id,
                      scriptResultId: row.original.id,
                    })
              }
            >
              {row.original.name}
            </Link>
          ) : null,
      },
      {
        id: "tags",
        header: "Tags",
        accessorKey: "tags",
        enableSorting: false,
        cell: ({ row }) =>
          !row.original.isHistory ? <>{row.original.tags}</> : null,
      },
      {
        id: "result",
        header: "Result",
        accessorKey: "result",
        enableSorting: false,
        cell: ({ row }) => (
          <>
            {expanded?.content === ScriptResultAction.VIEW_PREVIOUS_TESTS &&
            row.original.isHistory ? (
              <>
                <ScriptStatus status={row.original.status}>
                  {row.original.status_name}{" "}
                  <Link
                    data-testid="details-link"
                    to={
                      isMachine
                        ? urls.machines.machine.testing.scriptResult({
                            id: node.system_id,
                            scriptResultId: row.original.id,
                          })
                        : urls.controllers.controller.commissioning.scriptResult(
                            {
                              id: node.system_id,
                              scriptResultId: row.original.id,
                            }
                          )
                    }
                  >
                    View log
                  </Link>
                </ScriptStatus>
              </>
            ) : (
              <ScriptStatus status={row.original.status}>
                {row.original.status_name}
              </ScriptStatus>
            )}
          </>
        ),
      },
      {
        id: "date",
        header: "Date",
        accessorKey: "date",
        enableSorting: false,
        cell: ({ row }) => formatUtcDatetime(row.original.updated),
      },
      {
        id: "runtime",
        header: "Runtime",
        accessorKey: "runtime",
        enableSorting: false,
        cell: ({ row }) => <ScriptRunTime scriptResult={row.original} />,
      },
      {
        id: "metrics",
        header: "Metrics",
        accessorKey: "metrics",
        enableSorting: false,
        cell: ({ row }) =>
          row.original.hasMetrics ? (
            <Icon name="success"></Icon>
          ) : (
            <Icon name="minus"></Icon>
          ),
      },
      {
        id: "history",
        header: "",
        accessorKey: "history",
        enableSorting: false,
        cell: ({ row }) =>
          !row.original.isHistory ? (
            <Link
              data-testid="view-history-link"
              onClick={(e) => {
                e.preventDefault();
                setExpanded({
                  id: row.original.id,
                  content: ScriptResultAction.VIEW_PREVIOUS_TESTS,
                });
              }}
              to="#"
            >
              View previous tests
            </Link>
          ) : null,
      },
    ],
    [
      dispatch,
      expanded?.content,
      isMachine,
      node,
      sendAnalytics,
      setExpanded,
      showSuppressCol,
    ]
  );
};

export default useNodeTestsTableColumns;
