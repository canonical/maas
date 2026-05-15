import { useSelector } from "react-redux";

import ActionBar from "@/app/base/components/ActionBar";
import type { SetSearchFilter } from "@/app/base/types";
import { VMS_PER_PAGE } from "@/app/kvm/components/LXDVMsTable";
import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import vmClusterSelectors from "@/app/store/vmcluster/selectors";
import type { VMCluster, VMClusterMeta } from "@/app/store/vmcluster/types";

type Props = {
  clusterId: VMCluster[VMClusterMeta.PK];
  currentPage: number;
  searchFilter: string;
  setCurrentPage: (page: number) => void;
  setSearchFilter: SetSearchFilter;
  hosts: Pod[];
};

const LXDClusterHostsActionBar = ({
  clusterId,
  currentPage,
  searchFilter,
  setCurrentPage,
  setSearchFilter,
  hosts,
}: Props): React.ReactElement | null => {
  const cluster = useSelector((state: RootState) =>
    vmClusterSelectors.getById(state, clusterId)
  );
  const fetching = useSelector(vmClusterSelectors.loading);
  const getting = useSelector((state: RootState) =>
    vmClusterSelectors.status(state, "getting")
  );
  const loading = fetching || getting;

  if (!cluster) {
    return null;
  }

  return (
    <ActionBar
      currentPage={currentPage}
      itemCount={hosts.length}
      loading={loading}
      onSearchChange={setSearchFilter}
      pageSize={VMS_PER_PAGE}
      searchFilter={searchFilter}
      setCurrentPage={setCurrentPage}
    />
  );
};

export default LXDClusterHostsActionBar;
