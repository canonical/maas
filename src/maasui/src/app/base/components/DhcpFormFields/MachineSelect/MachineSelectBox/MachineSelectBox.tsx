import { useState } from "react";

import DebounceSearchBox from "@/app/base/components/DebounceSearchBox";
import { MachineSelectTable } from "@/app/base/components/MachineSelectTable/MachineSelectTable";
import MachineListPagination from "@/app/machines/views/MachineList/MachineListTable/MachineListPagination";
import type { FetchFilters, Machine } from "@/app/store/machine/types";
import { FilterGroupKey } from "@/app/store/machine/types";
import { useFetchMachines } from "@/app/store/machine/utils/hooks";

const MachineSelectBox = ({
  onSelect,
  pageSize = 5,
  filters,
}: {
  pageSize?: number;
  onSelect: (machine: Machine | null) => void;
  filters?: FetchFilters;
}): React.ReactElement => {
  const [searchText, setSearchText] = useState("");
  const [debouncedText, setDebouncedText] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const { machines, machineCount, loading, totalPages } = useFetchMachines({
    filters: {
      [FilterGroupKey.FreeText]: debouncedText,
      ...(filters ? filters : {}),
    },
    pagination: {
      currentPage,
      pageSize,
      setCurrentPage,
    },
  });
  return (
    <div className="machine-select-box">
      <DebounceSearchBox
        aria-label="Search by hostname, system ID or tags"
        autoComplete="off"
        autoFocus
        onDebounced={setDebouncedText}
        placeholder="Search by hostname, system ID or tags"
        role="combobox"
        searchText={searchText}
        setSearchText={setSearchText}
      />
      <div role="listbox">
        <MachineSelectTable
          machines={machines}
          machinesLoading={loading}
          onMachineClick={(machine) => {
            onSelect(machine);
          }}
          pageSize={pageSize}
          searchText={searchText}
          setSearchText={setSearchText}
        />
        <MachineListPagination
          currentPage={currentPage}
          itemsPerPage={pageSize}
          machineCount={machineCount}
          machinesLoading={loading}
          paginate={setCurrentPage}
          totalPages={totalPages}
        />
      </div>
    </div>
  );
};

export default MachineSelectBox;
