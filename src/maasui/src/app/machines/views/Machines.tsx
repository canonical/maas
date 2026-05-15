import type { ReactElement } from "react";
import { useCallback, useState } from "react";

import { useLocation, useNavigate } from "react-router";
import { useStorageState } from "react-storage-hooks";

import MachineListHeader from "./MachineList/MachineListHeader";
import { useGrouping, useResponsiveColumns } from "./MachineList/hooks";

import PageContent from "@/app/base/components/PageContent/PageContent";
import type { SyncNavigateFunction } from "@/app/base/types";
import MachineList from "@/app/machines/views/MachineList";
import { FilterMachines } from "@/app/store/machine/utils";

const Machines = (): ReactElement => {
  const navigate: SyncNavigateFunction = useNavigate();
  const location = useLocation();
  const currentFilters = FilterMachines.queryStringToFilters(location.search);

  const [searchFilter, setFilter] = useState(
    FilterMachines.filtersToString(currentFilters)
  );

  const setSearchFilter = useCallback(
    (searchText: string) => {
      setFilter(searchText);
      const filters = FilterMachines.getCurrentFilters(searchText);
      navigate(
        {
          search: FilterMachines.filtersToQueryString(filters),
        },
        { replace: true }
      );
    },
    [navigate, setFilter]
  );

  const [grouping, setGrouping] = useGrouping();

  const [hiddenColumns, setHiddenColumns] = useResponsiveColumns();

  const [hiddenGroups, setHiddenGroups] = useStorageState<(string | null)[]>(
    localStorage,
    "hiddenGroups",
    []
  );

  return (
    <PageContent
      header={
        <MachineListHeader
          grouping={grouping}
          hiddenColumns={hiddenColumns}
          searchFilter={searchFilter}
          setGrouping={setGrouping}
          setHiddenColumns={setHiddenColumns}
          setHiddenGroups={setHiddenGroups}
          setSearchFilter={setSearchFilter}
        />
      }
    >
      <MachineList
        grouping={grouping}
        hiddenColumns={hiddenColumns}
        hiddenGroups={hiddenGroups}
        searchFilter={searchFilter}
        setHiddenGroups={setHiddenGroups}
      />
    </PageContent>
  );
};

export default Machines;
