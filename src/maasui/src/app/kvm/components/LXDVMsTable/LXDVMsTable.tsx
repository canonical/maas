import type { ReactElement } from "react";
import { useCallback, useEffect, useState } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { usePrevious } from "@canonical/react-components";
import type { RowSelectionState, SortingState } from "@tanstack/react-table";
import { useDispatch, useSelector } from "react-redux";

import VMsActionBar from "./components/VMsActionBar";
import type {
  GetHostColumn,
  GetResources,
} from "./useVMsTableColumns/useVMsTableColumns";
import useVMsTableColumns from "./useVMsTableColumns/useVMsTableColumns";

import { useSidePanel } from "@/app/base/side-panel-context";
import type { SetSearchFilter } from "@/app/base/types";
import { SortDirection } from "@/app/base/types";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import { FilterGroupKey } from "@/app/store/machine/types";
import { FilterMachines, useFetchedCount } from "@/app/store/machine/utils";
import { useFetchMachines } from "@/app/store/machine/utils/hooks";
import type { Pod } from "@/app/store/pod/types";
import tagSelectors from "@/app/store/tag/selectors";

type Props = {
  displayForCluster?: boolean;
  getHostColumn?: GetHostColumn;
  getResources: GetResources;
  onAddVMClick?: () => void;
  pods: Pod["name"][];
  searchFilter: string;
  setSearchFilter: SetSearchFilter;
};

export const VMS_PER_PAGE = 10;

const LXDVMsTable = ({
  displayForCluster,
  getHostColumn,
  getResources,
  onAddVMClick,
  pods,
  searchFilter,
  setSearchFilter,
}: Props): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();

  const tags = useSelector(tagSelectors.all);
  const [currentPage, setCurrentPage] = useState(1);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [sorting, setSorting] = useState<SortingState>([
    { id: "hostname", desc: false },
  ]);

  const {
    callId,
    loading,
    machineCount,
    machines: vms,
  } = useFetchMachines({
    filters: {
      ...FilterMachines.parseFetchFilters(searchFilter),
      // Set the filters to get results that belong to this single pod or pods in a cluster.
      [FilterGroupKey.Pod]: pods,
    },
    sortDirection:
      sorting[0]?.desc === true
        ? SortDirection.DESCENDING
        : SortDirection.ASCENDING,
    sortKey: sorting[0]?.id ?? null,
    pagination: { currentPage, setCurrentPage, pageSize: VMS_PER_PAGE },
  });

  const selected = useSelector(machineSelectors.selected);
  const getSystemIdsFromRowSelection = useCallback(() => {
    const selectedVms = vms.filter((vm) =>
      Object.keys(rowSelection).includes(vm.id.toString())
    );
    return selectedVms.map((vm) => vm.system_id);
  }, [rowSelection, vms]);

  const count = useFetchedCount(machineCount, loading);
  const previousSearchFilter = usePrevious(searchFilter);

  useEffect(() => {
    // Clear machine selection and close the action form on filters change
    if (searchFilter !== previousSearchFilter) {
      closeSidePanel();
      dispatch(machineActions.setSelected(null));
    }
  }, [searchFilter, previousSearchFilter, closeSidePanel, dispatch]);

  useEffect(
    () => () => {
      // Clear machine selected state when unmounting.
      dispatch(machineActions.setSelected(null));
    },
    [dispatch]
  );

  useEffect(() => {
    const selectedSystemIds = getSystemIdsFromRowSelection();
    if (selected === null && selectedSystemIds.length > 0) {
      dispatch(
        machineActions.setSelected({
          items: selectedSystemIds,
        })
      );
    }

    if (selected && "items" in selected && !!selected.items) {
      const selectedCopy = [...selected.items];
      if (
        selectedCopy.sort().join(",") !== selectedSystemIds.sort().join(",")
      ) {
        dispatch(
          machineActions.setSelected({
            items: selectedSystemIds,
          })
        );
      }
    }
  }, [dispatch, getSystemIdsFromRowSelection, selected]);

  const columns = useVMsTableColumns({
    callId: callId,
    getHostColumn: getHostColumn,
    getResources: getResources,
    tags: tags,
  });
  return (
    <>
      <VMsActionBar
        currentPage={currentPage}
        onAddVMClick={onAddVMClick}
        searchFilter={searchFilter}
        setCurrentPage={setCurrentPage}
        setSearchFilter={setSearchFilter}
        vmCount={count}
      />
      <GenericTable
        aria-label="VMs table"
        className="vms-table"
        columns={columns}
        data={vms}
        isLoading={loading}
        noData={`No VMs in this ${displayForCluster ? "cluster" : "KVM host"} match the search criteria.`}
        selection={{
          rowSelection,
          setRowSelection,
          rowSelectionLabelKey: "hostname",
        }}
        setSorting={setSorting}
        sorting={sorting}
        variant="regular"
      />
    </>
  );
};

export default LXDVMsTable;
