import CPUPopover from "./CPUPopover";

import KVMResourceMeter from "@/app/kvm/components/KVMResourceMeter";
import type { KVMResource } from "@/app/kvm/types";
import { resourceWithOverCommit } from "@/app/store/pod/utils";

type Props = {
  cores: KVMResource;
  overCommit?: number;
};

const CPUColumn = ({
  cores,
  overCommit = 1,
}: Props): React.ReactElement | null => {
  const coresWithOver = resourceWithOverCommit(cores, overCommit);
  return (
    <CPUPopover cores={cores} overCommit={overCommit}>
      <KVMResourceMeter
        allocated={coresWithOver.allocated_tracked}
        free={coresWithOver.free}
        other={coresWithOver.allocated_other}
        segmented
      />
    </CPUPopover>
  );
};

export default CPUColumn;
