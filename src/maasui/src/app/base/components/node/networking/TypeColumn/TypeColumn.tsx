import DoubleRow from "@/app/base/components/DoubleRow";
import TooltipButton from "@/app/base/components/TooltipButton";
import type {
  NetworkInterface,
  NetworkLink,
  Node,
} from "@/app/store/types/node";
import { getInterfaceNumaNodes, getInterfaceTypeText } from "@/app/store/utils";

type Props = {
  link?: NetworkLink | null;
  nic?: NetworkInterface | null;
  node: Node;
};

const TypeColumn = ({ link, nic, node }: Props): React.ReactElement | null => {
  const numaNodes = getInterfaceNumaNodes(node, nic, link);
  const interfaceTypeDisplay = getInterfaceTypeText(node, nic, link, true);

  return (
    <DoubleRow
      data-testid="type"
      icon={
        numaNodes && numaNodes.length > 1 ? (
          <TooltipButton
            iconName="warning"
            message="This bond is spread over multiple NUMA nodes. This may lead to suboptimal performance."
            position="top-left"
          />
        ) : null
      }
      iconSpace={true}
      primary={interfaceTypeDisplay}
      secondary={numaNodes ? numaNodes.join(", ") : null}
    />
  );
};

export default TypeColumn;
