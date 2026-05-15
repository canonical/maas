import RAMPopover from "./RAMPopover";

import KVMResourceMeter from "@/app/kvm/components/KVMResourceMeter";
import type { KVMResource } from "@/app/kvm/types";
import { resourceWithOverCommit } from "@/app/store/pod/utils";

export type Props = {
  memory: {
    hugepages: KVMResource;
    general: KVMResource;
  };
  overCommit?: number;
};

const RAMColumn = ({
  memory,
  overCommit = 1,
}: Props): React.ReactElement | null => {
  const { general, hugepages } = memory;
  const generalOver = resourceWithOverCommit(general, overCommit);
  const allocated = generalOver.allocated_tracked + hugepages.allocated_tracked;
  const other = generalOver.allocated_other + hugepages.allocated_other;
  const free = generalOver.free + hugepages.free;

  return (
    <RAMPopover memory={memory} overCommit={overCommit}>
      <KVMResourceMeter
        allocated={allocated}
        binaryUnit
        free={free}
        other={other}
        unit="B"
      />
    </RAMPopover>
  );
};

export default RAMColumn;
