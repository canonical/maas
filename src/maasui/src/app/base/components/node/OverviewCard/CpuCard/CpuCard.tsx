import type { ReactElement } from "react";

import pluralize from "pluralize";

import TestResults from "@/app/base/components/node/TestResults";
import { HardwareType } from "@/app/base/enum";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import { nodeIsMachine } from "@/app/store/utils";

type CpuCardProps = {
  node: ControllerDetails | MachineDetails;
};

// Get the subtext for the CPU card. Only nodes commissioned after
// MAAS 2.4 will have the CPU speed.
const getCPUSubtext = (node: CpuCardProps["node"]) => {
  let text = "Unknown";

  if (node.cpu_count) {
    text = pluralize("core", node.cpu_count, true);
  }
  if (node.cpu_speed) {
    const speedText =
      node.cpu_speed > 1000
        ? `${node.cpu_speed / 1000} GHz`
        : `${node.cpu_speed} MHz`;
    text += `, ${speedText}`;
  }
  return text;
};

const CpuCard = ({ node }: CpuCardProps): ReactElement => (
  <>
    <div className="overview-card__cpu">
      <div className="u-flex--between">
        <strong className="p-muted-heading u-no-margin--bottom u-no-padding--top">
          CPU
        </strong>
        <small className="u-no-margin--bottom u-text--muted">
          {node.architecture}
        </small>
      </div>
      <h4 className="u-no-margin--bottom" data-testid="cpu-subtext">
        {getCPUSubtext(node)}
      </h4>
      <small className="u-text--muted">
        {node.metadata.cpu_model || "Unknown model"}
      </small>
    </div>
    {nodeIsMachine(node) ? (
      <TestResults hardwareType={HardwareType.CPU} machine={node} />
    ) : (
      <div className="overview-card__cpu-tests" />
    )}
  </>
);

export default CpuCard;
