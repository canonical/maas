import type { ReactElement } from "react";

import TestResults from "@/app/base/components/node/TestResults";
import { HardwareType } from "@/app/base/enum";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import { nodeIsMachine } from "@/app/store/utils";

type MemoryCardProps = {
  node: ControllerDetails | MachineDetails;
};

const MemoryCard = ({ node }: MemoryCardProps): ReactElement => (
  <>
    <div className="overview-card__memory">
      <strong className="p-muted-heading u-flex--between u-no-margin--bottom u-no-padding--top">
        Memory
      </strong>
      <h4 className="u-no-margin--bottom">
        {node.memory ? node.memory + " GiB" : "Unknown"}
      </h4>
    </div>
    {nodeIsMachine(node) ? (
      <TestResults hardwareType={HardwareType.Memory} machine={node} />
    ) : (
      <div className="overview-card__memory-tests" />
    )}
  </>
);

export default MemoryCard;
