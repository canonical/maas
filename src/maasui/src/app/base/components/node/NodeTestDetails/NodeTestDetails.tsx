import { useEffect, useState } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { Col, Row, Spinner, Tooltip } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { Link } from "react-router";

import NodeTestDetailsLogs from "./NodeTestDetailsLogs";
import useNodeTestDetailsTableColumns from "./useNodeTestDetailsTableColumns/useNodeTestDetailsTableColumns";

import { useGetURLId } from "@/app/base/hooks/urls";
import type { RootState } from "@/app/store/root/types";
import { scriptResultActions } from "@/app/store/scriptresult";
import scriptResultSelectors from "@/app/store/scriptresult/selectors";
import type { ScriptResultResult } from "@/app/store/scriptresult/types";
import {
  ScriptResultMeta,
  ScriptResultDataType,
} from "@/app/store/scriptresult/types";
import { isId } from "@/app/utils";

type Props = {
  getReturnPath: (id: string) => string;
};

const NodeTestDetails = ({
  getReturnPath,
}: Props): React.ReactElement | null => {
  const [fetched, setFetched] = useState(false);
  const dispatch = useDispatch();
  const id = useGetURLId("system_id");
  const scriptResultId = useGetURLId(ScriptResultMeta.PK, "scriptResultId");
  const result = useSelector((state: RootState) =>
    scriptResultSelectors.getById(state, scriptResultId)
  );
  const logs = useSelector(scriptResultSelectors.logs);
  const loading = useSelector(scriptResultSelectors.loading);
  const log = logs && isId(scriptResultId) ? logs[scriptResultId] : null;
  const columns = useNodeTestDetailsTableColumns();

  useEffect(() => {
    if (!fetched && isId(scriptResultId)) {
      dispatch(scriptResultActions.get(scriptResultId));
      setFetched(true);
    }
  }, [dispatch, scriptResultId, fetched, setFetched]);

  useEffect(() => {
    if (!(logs && isId(scriptResultId) && logs[scriptResultId]) && result) {
      [
        ScriptResultDataType.COMBINED,
        ScriptResultDataType.STDOUT,
        ScriptResultDataType.STDERR,
        ScriptResultDataType.RESULT,
      ].forEach((type) =>
        dispatch(scriptResultActions.getLogs(result.id, type))
      );
    }
  }, [dispatch, result, logs, scriptResultId]);

  if (loading) {
    return <Spinner />;
  } else if (!result || !isId(id)) {
    return <h4 data-testid="not-found">Script result could not be found.</h4>;
  }

  const hasMetrics = result.results.length > 0;
  const returnPath = getReturnPath(id);
  const data = [
    {
      ...result,
      id: result.id,
      status: result.status,
      status_name: result.status_name,
      exit_status: result.exit_status,
      tags: result.tags,
      started: result.started,
      ended: result.ended,
      runtime: result.runtime,
    },
  ];
  return (
    <>
      <Row className="u-sv2">
        <Col size={8}>
          <h2 className="p-heading--4">{result.name} details</h2>
        </Col>
        <Col className="u-align--right" size={4}>
          <Link data-testid="return-link" to={returnPath}>
            &lsaquo; Back to test results
          </Link>
        </Col>
      </Row>
      <GenericTable
        columns={columns}
        data={data}
        isLoading={false}
        noData="No details available."
      />
      {hasMetrics ? (
        <Row>
          <Col size={12}>
            <h4>Metrics</h4>
            <table data-testid="script-details-metrics" role="grid">
              <tbody>
                {result.results.map((item: ScriptResultResult) => (
                  <tr key={`metric-${item.name}`} role="row">
                    <td role="gridcell">
                      <Tooltip message={item.description}>{item.title}</Tooltip>
                    </td>
                    <td role="gridcell">{item.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Col>
        </Row>
      ) : null}
      {log ? (
        <Row>
          <Col size={12}>
            <h4>Output</h4>
            <NodeTestDetailsLogs log={log} />
          </Col>
        </Row>
      ) : null}
    </>
  );
};

export default NodeTestDetails;
