import type { ContextualMenuProps } from "@canonical/react-components";
import type { LinkProps } from "react-router";
import { Link } from "react-router";

import {
  ScriptResultAction,
  type SetExpanded,
} from "../components/useNodeTestsTableColumns/useNodeTestsTableColumns";

import TableMenu from "@/app/base/components/TableMenu";
import { useSendAnalytics } from "@/app/base/hooks";
import type { DataTestElement } from "@/app/base/types";
import urls from "@/app/base/urls";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { ScriptResult } from "@/app/store/scriptresult/types";
import { ScriptResultType } from "@/app/store/scriptresult/types";
import { scriptResultInProgress } from "@/app/store/scriptresult/utils";
import { nodeIsMachine } from "@/app/store/utils";

type Props = {
  node: ControllerDetails | MachineDetails;
  resultType: ScriptResultType.COMMISSIONING | ScriptResultType.TESTING;
  scriptResult: ScriptResult;
  setExpanded: SetExpanded;
};

type LinkWithDataTest = DataTestElement<LinkProps>;

const TestActions = ({
  node,
  resultType,
  scriptResult,
  setExpanded,
}: Props): React.ReactElement => {
  const sendAnalytics = useSendAnalytics();
  const canViewDetails = !scriptResultInProgress(scriptResult.status);
  const hasMetrics = scriptResult.results.length > 0;
  const links: ContextualMenuProps<LinkWithDataTest>["links"] = [];
  const isTesting = resultType === ScriptResultType.TESTING;
  const isMachine = nodeIsMachine(node);
  const detailsURL = isMachine
    ? isTesting
      ? urls.machines.machine.testing.scriptResult
      : urls.machines.machine.commissioning.scriptResult
    : urls.controllers.controller.commissioning.scriptResult;

  if (canViewDetails) {
    links.push({
      children: "View details...",
      "data-testid": "view-details",
      element: Link,
      to: detailsURL({
        id: node.system_id,
        scriptResultId: scriptResult.id,
      }),
    });
  }

  links.push({
    children: "View previous tests...",
    "data-testid": "view-previous-tests",
    onClick: () => {
      setExpanded({
        id: scriptResult.id,
        content: ScriptResultAction.VIEW_PREVIOUS_TESTS,
      });
      sendAnalytics(
        `${node.node_type_display} ${isTesting ? "testing" : "commissioning"}`,
        "View testing script history",
        "View previous tests"
      );
    },
  });

  if (hasMetrics) {
    links.push({
      children: "View metrics...",
      "data-testid": "view-metrics",
      onClick: () => {
        setExpanded({
          id: scriptResult.id,
          content: ScriptResultAction.VIEW_METRICS,
        });
        sendAnalytics(
          `${node.node_type_display} ${
            resultType === ScriptResultType.TESTING
              ? "testing"
              : "commissioning"
          }`,
          "View testing script metrics",
          "View metrics"
        );
      },
    });
  }

  return <TableMenu links={links} position="right" title="Take action:" />;
};

export default TestActions;
