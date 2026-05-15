import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import CoreResources from "../CoreResources";
import RamResources from "../RamResources";
import VfResources from "../VfResources";
import VmResources from "../VmResources";

import urls from "@/app/base/urls";
import { FilterGroupKey } from "@/app/store/machine/types";
import { useFetchMachineCount } from "@/app/store/machine/utils/hooks";
import { PodType } from "@/app/store/pod/constants";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import { resourceWithOverCommit } from "@/app/store/pod/utils";
import type { RootState } from "@/app/store/root/types";

type Props = { id: Pod["id"] };

const KVMResourcesCard = ({ id }: Props): React.ReactElement => {
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, id)
  );

  const { machineCount } = useFetchMachineCount({
    [FilterGroupKey.Pod]: pod ? [pod.name] : [],
  });

  if (pod) {
    const {
      cpu_over_commit_ratio,
      memory_over_commit_ratio,
      resources: {
        cores,
        interfaces,
        memory: { general, hugepages },
      },
    } = pod;
    const coresWithOver = resourceWithOverCommit(cores, cpu_over_commit_ratio);
    const generalWithOver = resourceWithOverCommit(
      general,
      memory_over_commit_ratio
    );

    return (
      <>
        <div className="kvm-resources-card">
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
          <VfResources dynamicLayout interfaces={interfaces} />
        </div>
        {pod.type === PodType.LXD ? (
          <div className="vms-link">
            <Link to={urls.kvm.lxd.single.vms({ id })}>
              Total VMs: {machineCount ?? 0}
            </Link>
          </div>
        ) : (
          <VmResources podId={id} />
        )}
      </>
    );
  }
  return <Spinner text="Loading" />;
};

export default KVMResourcesCard;
