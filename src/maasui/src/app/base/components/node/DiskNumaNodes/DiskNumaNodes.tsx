import TooltipButton from "@/app/base/components/TooltipButton";
import type { Disk } from "@/app/store/types/node";

type Props = { disk: Disk };

const DiskNumaNodes = ({ disk }: Props): React.ReactElement => {
  let numaNodes: number[] = [];
  if ("numa_nodes" in disk && disk.numa_nodes !== undefined) {
    numaNodes = disk.numa_nodes;
  } else if ("numa_node" in disk && disk.numa_node !== undefined) {
    numaNodes = [disk.numa_node];
  }

  return (
    <>
      {numaNodes.length > 1 && (
        <TooltipButton
          className="u-nudge-left--x-small"
          iconName="warning"
          message={
            "This volume is spread over multiple NUMA nodes which may cause suboptimal performance."
          }
        />
      )}
      <span data-testid="numa-nodes">{numaNodes.join(", ") || "—"}</span>
    </>
  );
};

export default DiskNumaNodes;
