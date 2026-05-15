import { useState } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import type { SortingState } from "@tanstack/react-table";
import { useSelector } from "react-redux";

import useVirshTableColumns from "./useVirshTableColumns/useVirshTableColumns";

import { useGetPool } from "@/app/api/query/pools";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import "./_index.scss";

export type VirshTableRow = {
  id: number;
  name: string;
  resources: number;
  tags: string[];
  pool: string | undefined;
  cpu: number;
  ram: number;
  storage: number;
  kvm: Pod;
};

const generateVirshTableRowData = (kvms: Pod[]): VirshTableRow[] => {
  const data: VirshTableRow[] = [];

  kvms.forEach((kvm) => {
    if (!kvm) return;
    data.push({
      id: kvm.id,
      name: kvm.name,
      resources: kvm.resources.vm_count.tracked,
      tags: kvm.tags,
      pool: useGetPool({ path: { resource_pool_id: kvm.pool! } }).data?.name,
      cpu: kvm.resources.cores.allocated_tracked,
      ram:
        kvm.resources.memory.general.allocated_tracked +
        kvm.resources.memory.hugepages.allocated_tracked,
      storage: kvm.resources.storage.allocated_tracked,
      kvm,
    });
  });

  return data;
};

const VirshTable = () => {
  const virshKvms = useSelector(podSelectors.virsh);
  const [sorting, setSorting] = useState<SortingState>([
    { id: "name", desc: true },
  ]);
  const columns = useVirshTableColumns();
  const data = generateVirshTableRowData(virshKvms);

  return (
    <GenericTable<VirshTableRow>
      aria-label="virsh table"
      className="virsh-table"
      columns={columns}
      data={data}
      isLoading={false}
      noData="No pods available."
      setSorting={setSorting}
      sorting={sorting}
      variant="regular"
    />
  );
};

export default VirshTable;
