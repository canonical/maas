import ControllerLink from "@/app/base/components/ControllerLink";
import DeviceLink from "@/app/base/components/DeviceLink";
import MachineLink from "@/app/base/components/MachineLink";
import type { Node } from "@/app/store/types/node";
import { NodeType } from "@/app/store/types/node";

type Props = {
  nodeType: NodeType;
  systemId?: Node["system_id"] | null;
};

const NodeLink = ({ nodeType, systemId }: Props): React.ReactElement | null => {
  switch (nodeType) {
    case NodeType.DEFAULT:
    case NodeType.MACHINE:
      return <MachineLink systemId={systemId} />;
    case NodeType.DEVICE:
      return <DeviceLink systemId={systemId} />;
    case NodeType.RACK_CONTROLLER:
    case NodeType.REGION_CONTROLLER:
    case NodeType.REGION_AND_RACK_CONTROLLER:
      return <ControllerLink systemId={systemId} />;
    default:
      return null;
  }
};

export default NodeLink;
