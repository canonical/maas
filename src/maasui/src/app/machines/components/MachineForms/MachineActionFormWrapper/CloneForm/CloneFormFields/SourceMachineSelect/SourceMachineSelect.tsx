import type { ReactNode } from "react";
import { useState } from "react";

import { Notification as NotificationBanner } from "@canonical/react-components";
import classNames from "classnames";

import SourceMachineDetails from "./SourceMachineDetails";

import DebounceSearchBox from "@/app/base/components/DebounceSearchBox";
import { MachineSelectTable } from "@/app/base/components/MachineSelectTable/MachineSelectTable";
import { useFetchActions } from "@/app/base/hooks";
import MachineListPagination from "@/app/machines/views/MachineList/MachineListTable/MachineListPagination";
import type { Machine, MachineDetails } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import { useFetchMachines } from "@/app/store/machine/utils/hooks";
import { tagActions } from "@/app/store/tag";

export enum Label {
  Loading = "Loading...",
  NoSourceMachines = "No source machine available",
}

type Props = {
  className?: string;
  loadingMachineDetails?: boolean;
  pageSize?: number;
  onMachineClick: (machine: Machine | null) => void;
  selectedMachine?: MachineDetails | null;
};

export const SourceMachineSelect = ({
  className,
  pageSize = 5,
  loadingMachineDetails = false,
  onMachineClick,
  selectedMachine = null,
}: Props): React.ReactElement => {
  const [searchText, setSearchText] = useState("");
  const [debouncedText, setDebouncedText] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  // We filter by a subset of machine parameters rather than using the search
  // selector, because the search selector will match parameters that aren't
  // included in the clone source table.
  const { machines, machineCount, loading, totalPages } = useFetchMachines({
    filters: FilterMachines.parseFetchFilters(debouncedText),
    pagination: {
      currentPage,
      pageSize,
      setCurrentPage,
    },
  });

  useFetchActions([tagActions.fetch]);

  let content: ReactNode;
  if (loadingMachineDetails || selectedMachine) {
    content = <SourceMachineDetails machine={selectedMachine} />;
  } else if (!loading && machineCount === 0) {
    content = (
      <NotificationBanner
        borderless
        severity="negative"
        title={Label.NoSourceMachines}
      >
        All machines are selected as destination machines. Unselect at least one
        machine from the list.
      </NotificationBanner>
    );
  } else {
    content = (
      <>
        <MachineSelectTable
          machines={machines}
          machinesLoading={loading}
          onMachineClick={onMachineClick}
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
          truncateThreshold={6}
        />
      </>
    );
  }
  return (
    <div className={classNames("source-machine-select", className)}>
      <DebounceSearchBox
        aria-label="Search by hostname, system ID or tags"
        autoComplete="off"
        onChange={() => {
          // Unset the selected machine if the search input changes - assume
          // the user wants to change it.
          if (selectedMachine) {
            onMachineClick(null);
          }
        }}
        onDebounced={setDebouncedText}
        placeholder="Search by hostname, system ID or tags"
        role="combobox"
        searchText={searchText}
        setSearchText={setSearchText}
      />
      {content}
    </div>
  );
};

export default SourceMachineSelect;
