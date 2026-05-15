import { useCallback, useState } from "react";

import type { RowSelectionState } from "@tanstack/react-table";
import { useSelector } from "react-redux";
import { useLocation, useNavigate } from "react-router";

import ControllerListHeader from "./ControllerListHeader";
import ControllersTable from "./components/ControllersTable";

import PageContent from "@/app/base/components/PageContent/PageContent";
import VaultNotification from "@/app/base/components/VaultNotification";
import { useFetchActions, useWindowTitle } from "@/app/base/hooks";
import type { SyncNavigateFunction } from "@/app/base/types";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors from "@/app/store/controller/selectors";
import { FilterControllers } from "@/app/store/controller/utils";
import { generalActions } from "@/app/store/general";
import { vaultEnabled as vaultEnabledSelectors } from "@/app/store/general/selectors";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";

const ControllerList = (): React.ReactElement => {
  const navigate: SyncNavigateFunction = useNavigate();
  const location = useLocation();
  const currentFilters = FilterControllers.queryStringToFilters(
    location.search
  );
  const [searchFilter, setFilter] = useState(
    // Initialise the filter state from the URL.
    FilterControllers.filtersToString(currentFilters)
  );
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const selectedIDs = useSelector(controllerSelectors.selectedIDs);

  const filteredControllers = useSelector((state: RootState) =>
    controllerSelectors.search(state, searchFilter || null, selectedIDs)
  );
  const controllersLoading = useSelector(controllerSelectors.loading);
  const vaultEnabledLoading = useSelector(vaultEnabledSelectors.loading);
  useWindowTitle("Controllers");

  useFetchActions([
    controllerActions.fetch,
    tagActions.fetch,
    generalActions.fetchVaultEnabled,
  ]);

  // Update the URL when filters are changed.
  const setSearchFilter = useCallback(
    (searchText: string) => {
      setFilter(searchText);
      const filters = FilterControllers.getCurrentFilters(searchText);
      navigate({
        search: FilterControllers.filtersToQueryString(filters),
      });
    },
    [navigate, setFilter]
  );

  return (
    <PageContent
      header={
        <ControllerListHeader
          rowSelection={rowSelection}
          searchFilter={searchFilter}
          setSearchFilter={setSearchFilter}
        />
      }
    >
      <VaultNotification />
      <ControllersTable
        controllers={filteredControllers}
        isPending={controllersLoading || vaultEnabledLoading}
        rowSelection={rowSelection}
        setRowSelection={setRowSelection}
      />
    </PageContent>
  );
};

export default ControllerList;
