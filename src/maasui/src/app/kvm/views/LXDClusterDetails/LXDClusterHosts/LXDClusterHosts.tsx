import { useCallback, useState } from "react";

import { Strip } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { useLocation, useNavigate } from "react-router";

import LXDClusterSummaryCard from "../LXDClusterSummaryCard";

import LXDClusterHostsActionBar from "./LXDClusterHostsActionBar";
import LXDClusterHostsTable from "./LXDClusterHostsTable";

import { useFetchActions, useWindowTitle } from "@/app/base/hooks";
import type { SetSearchFilter, SyncNavigateFunction } from "@/app/base/types";
import { FilterMachines } from "@/app/store/machine/utils";
import podSelectors from "@/app/store/pod/selectors";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import vmClusterSelectors from "@/app/store/vmcluster/selectors";
import type { VMCluster } from "@/app/store/vmcluster/types";

type Props = {
  clusterId: VMCluster["id"];
};

export enum Label {
  Title = "LXD cluster hosts",
}

const LXDClusterHosts = ({ clusterId }: Props): React.ReactElement => {
  const navigate: SyncNavigateFunction = useNavigate();
  const location = useLocation();
  const cluster = useSelector((state: RootState) =>
    vmClusterSelectors.getById(state, clusterId)
  );
  const [currentPage, setCurrentPage] = useState(1);
  // Search filter is determined by the URL and used to initialise state.
  const currentFilters = FilterMachines.queryStringToFilters(location.search);
  const [searchFilter, setFilter] = useState<string>(
    FilterMachines.filtersToString(currentFilters)
  );
  const hosts = useSelector((state: RootState) =>
    podSelectors.searchInCluster(state, clusterId, searchFilter)
  );
  useWindowTitle(`${cluster?.name || "LXD cluster"} KVM hosts`);

  useFetchActions([tagActions.fetch]);

  const setSearchFilter: SetSearchFilter = useCallback(
    (searchFilter: string) => {
      setFilter(searchFilter);
      const filters = FilterMachines.getCurrentFilters(searchFilter);
      navigate({ search: FilterMachines.filtersToQueryString(filters) });
    },
    [setFilter, navigate]
  );

  return (
    <div aria-label={Label.Title}>
      <Strip shallow>
        <LXDClusterSummaryCard clusterId={clusterId} />
      </Strip>
      <LXDClusterHostsActionBar
        clusterId={clusterId}
        currentPage={currentPage}
        hosts={hosts}
        searchFilter={searchFilter}
        setCurrentPage={setCurrentPage}
        setSearchFilter={setSearchFilter}
      />
      <LXDClusterHostsTable
        clusterId={clusterId}
        currentPage={currentPage}
        hosts={hosts}
        searchFilter={searchFilter}
      />
    </div>
  );
};

export default LXDClusterHosts;
