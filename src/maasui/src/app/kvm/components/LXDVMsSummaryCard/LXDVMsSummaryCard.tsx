import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import CoreResources from "@/app/kvm/components/CoreResources";
import RamResources from "@/app/kvm/components/RamResources";
import StorageResources from "@/app/kvm/components/StorageResources";
import VfResources from "@/app/kvm/components/VfResources";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import { resourceWithOverCommit } from "@/app/store/pod/utils";
import type { RootState } from "@/app/store/root/types";

type Props = {
  id: Pod["id"];
};

const LXDVMsSummaryCard = ({ id }: Props): React.ReactElement => {
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, id)
  );

  if (!pod) {
    return <Spinner text="Loading..." />;
  }

  const {
    cpu_over_commit_ratio,
    default_storage_pool,
    memory_over_commit_ratio,
    resources: {
      cores,
      interfaces,
      memory: { general, hugepages },
      storage,
      storage_pools,
    },
  } = pod;
  const coresWithOver = resourceWithOverCommit(cores, cpu_over_commit_ratio);
  const generalWithOver = resourceWithOverCommit(
    general,
    memory_over_commit_ratio
  );

  return (
    <div className="lxd-vms-summary-card">
      <RamResources
        dynamicLayout
        generalAllocated={generalWithOver.allocated_tracked}
        generalFree={generalWithOver.free}
        generalOther={generalWithOver.allocated_other}
        hugepagesAllocated={hugepages.allocated_tracked}
        hugepagesFree={hugepages.free}
        hugepagesOther={hugepages.allocated_other}
      />
      <CoreResources
        allocated={coresWithOver.allocated_tracked}
        dynamicLayout
        free={coresWithOver.free}
        other={coresWithOver.allocated_other}
      />
      <StorageResources
        allocated={storage.allocated_tracked}
        defaultPoolId={default_storage_pool}
        free={storage.free}
        other={storage.allocated_other}
        pools={storage_pools}
      />
      <VfResources interfaces={interfaces} />
    </div>
  );
};

export default LXDVMsSummaryCard;
