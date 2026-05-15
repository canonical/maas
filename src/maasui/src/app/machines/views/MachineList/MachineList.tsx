import { useEffect, useState } from "react";

import type { ValueOf } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import ErrorsNotification from "./ErrorsNotification";
import MachineListTable from "./MachineListTable";
import { DEFAULTS } from "./MachineListTable/constants";
import { usePageSize, type useResponsiveColumns } from "./hooks";

import VaultNotification from "@/app/base/components/VaultNotification";
import { useFetchActions, useWindowTitle } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { SortDirection } from "@/app/base/types";
import { controllerActions } from "@/app/store/controller";
import { generalActions } from "@/app/store/general";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { FetchGroupKey } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import { useFetchMachines } from "@/app/store/machine/utils/hooks";

type Props = {
  grouping: FetchGroupKey | null;
  hiddenColumns: ReturnType<typeof useResponsiveColumns>[0];
  hiddenGroups: (string | null)[];
  searchFilter: string;
  setHiddenGroups: (groups: (string | null)[]) => void;
};

const MachineList = ({
  grouping,
  hiddenColumns,
  hiddenGroups,
  searchFilter,
  setHiddenGroups,
}: Props): React.ReactElement => {
  useWindowTitle("Machines");
  const dispatch = useDispatch();
  const { isOpen: headerFormOpen } = useSidePanel();
  const errors = useSelector(machineSelectors.errors);
  const [currentPage, setCurrentPage] = useState(1);
  const [sortKey, setSortKey] = useState<FetchGroupKey | null>(
    DEFAULTS.sortKey
  );
  const [sortDirection, setSortDirection] = useState<
    ValueOf<typeof SortDirection>
  >(DEFAULTS.sortDirection);

  const [pageSize, setPageSize] = usePageSize();

  const {
    callId,
    groups,
    loading,
    machineCount,
    machines,
    machinesErrors,
    totalPages,
  } = useFetchMachines({
    collapsedGroups: hiddenGroups,
    filters: FilterMachines.parseFetchFilters(searchFilter),
    grouping,
    sortDirection,
    sortKey,
    pagination: { currentPage, setCurrentPage, pageSize },
  });

  useEffect(
    () => () => {
      // Clear machine selected state and clean up any machine errors etc.
      // when closing the list.
      dispatch(machineActions.setSelected(null));
      dispatch(machineActions.cleanup());
    },
    [dispatch]
  );

  // Fetch vault enabled status and controllers on page load
  useFetchActions([controllerActions.fetch, generalActions.fetchVaultEnabled]);

  return (
    <>
      {errors && !headerFormOpen ? (
        <ErrorsNotification
          errors={errors}
          onAfterDismiss={() => dispatch(machineActions.cleanup())}
        />
      ) : null}
      {!headerFormOpen ? <ErrorsNotification errors={machinesErrors} /> : null}
      <VaultNotification />
      <MachineListTable
        callId={callId}
        currentPage={currentPage}
        filter={searchFilter}
        grouping={grouping}
        groups={groups}
        hiddenColumns={hiddenColumns}
        hiddenGroups={hiddenGroups}
        machineCount={machineCount}
        machines={machines}
        machinesLoading={loading}
        pageSize={pageSize}
        setCurrentPage={setCurrentPage}
        setHiddenGroups={setHiddenGroups}
        setPageSize={setPageSize}
        setSortDirection={setSortDirection}
        setSortKey={setSortKey}
        sortDirection={sortDirection}
        sortKey={sortKey}
        totalPages={totalPages}
      />
    </>
  );
};

export default MachineList;
