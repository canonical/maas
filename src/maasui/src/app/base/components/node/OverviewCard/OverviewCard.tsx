import type { ReactElement } from "react";

import { Card } from "@canonical/react-components";

import ControllerStatusCard from "./ControllerStatusCard";
import CpuCard from "./CpuCard";
import DetailsCard from "./DetailsCard";
import MachineStatusCard from "./MachineStatusCard";
import MemoryCard from "./MemoryCard";
import StorageCard from "./StorageCard";

import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import { nodeIsMachine } from "@/app/store/utils";

type OverviewCardProps = {
  node: ControllerDetails | MachineDetails;
};

const OverviewCard = ({ node }: OverviewCardProps): ReactElement => {
  const isMachine = nodeIsMachine(node);
  return (
    <Card className="u-no-padding">
      <div className="overview-card">
        {isMachine ? (
          <MachineStatusCard machine={node} />
        ) : (
          <ControllerStatusCard controller={node} />
        )}
        <CpuCard node={node} />
        <MemoryCard node={node} />
        <StorageCard node={node} />
        <DetailsCard node={node} />
      </div>
    </Card>
  );
};

export default OverviewCard;
