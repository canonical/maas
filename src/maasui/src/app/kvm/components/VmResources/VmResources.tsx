import { useState } from "react";

import type { ValueOf } from "@canonical/react-components";
import { ContextualMenu } from "@canonical/react-components";
import { useSelector } from "react-redux";

import type { SortDirection } from "@/app/base/types";
import MachineListTable from "@/app/machines/views/MachineList/MachineListTable";
import { DEFAULTS } from "@/app/machines/views/MachineList/MachineListTable/constants";
import type { FetchFilters, FetchGroupKey } from "@/app/store/machine/types";
import { FilterGroupKey } from "@/app/store/machine/types";
import { useFetchedCount } from "@/app/store/machine/utils";
import { useFetchMachines } from "@/app/store/machine/utils/hooks";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";

export enum Label {
  ResourceVMs = "Resource VMs",
}

export type Props = {
  filters?: FetchFilters;
  podId: Pod["id"];
};

export const VMS_PER_PAGE = 5;

const VmResources = ({ filters, podId }: Props): React.ReactElement => {
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, podId)
  );
  const [currentPage, setCurrentPage] = useState(1);
  const [sortKey, setSortKey] = useState<FetchGroupKey | null>(
    DEFAULTS.sortKey
  );
  const [sortDirection, setSortDirection] = useState<
    ValueOf<typeof SortDirection>
  >(DEFAULTS.sortDirection);
  const {
    callId,
    loading,
    machineCount,
    machines: vms,
    groups,
    totalPages,
  } = useFetchMachines({
    filters: {
      ...filters,
      [FilterGroupKey.Pod]: pod ? [pod.name] : [],
    },
    sortDirection,
    sortKey,
    pagination: {
      currentPage,
      setCurrentPage,
      pageSize: VMS_PER_PAGE,
    },
  });
  const count = useFetchedCount(machineCount, loading);
  return (
    <div className="vm-resources">
      <div className="vm-resources__dropdown-container">
        <ContextualMenu
          dropdownClassName="vm-resources__dropdown"
          position="left"
          toggleAppearance="link"
          toggleClassName="vm-resources__toggle is-dense"
          toggleDisabled={!count}
          toggleLabel={`Total VMs: ${count ?? 0}`}
          toggleProps={{ position: "left", "aria-label": Label.ResourceVMs }}
        >
          <MachineListTable
            callId={callId}
            currentPage={currentPage}
            groups={groups}
            hiddenColumns={[
              "owner",
              "pool",
              "zone",
              "fabric",
              "disks",
              "storage",
            ]}
            machineCount={machineCount}
            machines={vms}
            machinesLoading={loading}
            pageSize={VMS_PER_PAGE}
            setCurrentPage={setCurrentPage}
            setSortDirection={setSortDirection}
            setSortKey={setSortKey}
            showActions={false}
            sortDirection={sortDirection}
            sortKey={sortKey}
            totalPages={totalPages}
          />
        </ContextualMenu>
      </div>
    </div>
  );
};

export default VmResources;
