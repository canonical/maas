import { Spinner } from "@canonical/react-components";
import classNames from "classnames";
import { useSelector } from "react-redux";

import CoreResources from "@/app/kvm/components/CoreResources";
import RamResources from "@/app/kvm/components/RamResources";
import StorageResources from "@/app/kvm/components/StorageResources";
import VfResources from "@/app/kvm/components/VfResources";
import podSelectors from "@/app/store/pod/selectors";
import type { PodNetworkInterface } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import vmClusterSelectors from "@/app/store/vmcluster/selectors";
import type { VMCluster } from "@/app/store/vmcluster/types";

type Props = {
  clusterId: VMCluster["id"];
  showStorage?: boolean;
};

const LXDClusterSummaryCard = ({
  clusterId,
  showStorage = true,
}: Props): React.ReactElement | null => {
  const cluster = useSelector((state: RootState) =>
    vmClusterSelectors.getById(state, clusterId)
  );
  const clusterHosts = useSelector((state: RootState) =>
    podSelectors.lxdHostsInClusterById(state, clusterId)
  );
  const podsLoading = useSelector(podSelectors.loading);

  if (podsLoading) {
    return <Spinner text="Loading..." />;
  }

  if (!cluster) {
    return null;
  }

  const {
    cpu,
    memory: { general, hugepages },
    storage,
    storage_pools,
  } = cluster.total_resources;
  const interfaces = clusterHosts.reduce<PodNetworkInterface[]>(
    (interfaces, host) => {
      host.resources.interfaces.forEach((hostIface) => {
        const existingIface = interfaces.find(
          (iface) => iface.id === hostIface.id
        );
        if (!existingIface) {
          interfaces.push(hostIface);
        }
      });
      return interfaces;
    },
    []
  );
  return (
    <div
      className={classNames("lxd-cluster-summary-card", {
        "show-storage": showStorage,
      })}
    >
      <RamResources
        dynamicLayout
        generalAllocated={general.allocated_tracked}
        generalFree={general.free}
        generalOther={general.allocated_other}
        hugepagesAllocated={hugepages.allocated_tracked}
        hugepagesFree={hugepages.free}
        hugepagesOther={hugepages.allocated_other}
      />
      <CoreResources
        allocated={cpu.allocated_tracked}
        dynamicLayout
        free={cpu.free}
        other={cpu.allocated_other}
      />
      {showStorage && (
        <StorageResources
          allocated={storage.allocated_tracked}
          free={storage.free}
          other={storage.allocated_other}
          pools={storage_pools}
        />
      )}
      <VfResources dynamicLayout interfaces={interfaces} showAggregated />
    </div>
  );
};

export default LXDClusterSummaryCard;
