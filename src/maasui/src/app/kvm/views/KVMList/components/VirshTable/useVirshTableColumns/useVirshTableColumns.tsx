import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import type { VirshTableRow } from "../VirshTable";

import urls from "@/app/base/urls";
import CPUColumn from "@/app/kvm/components/CPUColumn";
import NameColumn from "@/app/kvm/components/NameColumn";
import PoolColumn from "@/app/kvm/components/PoolColumn";
import RAMColumn from "@/app/kvm/components/RAMColumn";
import StorageColumn from "@/app/kvm/components/StorageColumn";
import TagsColumn from "@/app/kvm/components/TagsColumn";
import VMsColumn from "@/app/kvm/components/VMsColumn";

type VirshColumnDef = ColumnDef<VirshTableRow, Partial<VirshTableRow>>;

const useVirshTableColumns = (): VirshColumnDef[] => {
  return useMemo(
    () => [
      {
        id: "name",
        header: () => (
          <>
            Name
            <br />
            Address
          </>
        ),
        accessorKey: "name",
        enableSorting: true,
        cell: ({ row }) => (
          <NameColumn
            name={row.original.name}
            secondary={row.original.kvm.power_parameters?.power_address}
            url={urls.kvm.virsh.details.index({ id: row.original.id })}
          />
        ),
      },
      {
        id: "resources",
        header: "VMs",
        accessorKey: "resources",
        enableSorting: true,
        cell: ({ row }) => <VMsColumn vms={row.original.resources} />,
      },
      {
        id: "tags",
        header: "TAGS",
        accessorKey: "tags",
        enableSorting: false,
        cell: ({ row }) => <TagsColumn tags={row.original.tags} />,
      },
      {
        id: "pool",
        header: () => (
          <>
            Resource pool
            <br />
            AZ
          </>
        ),
        accessorKey: "pool",
        enableSorting: true,
        cell: ({ row }) => (
          <PoolColumn
            poolId={row.original.kvm.pool}
            zoneId={row.original.kvm.zone}
          />
        ),
      },
      {
        id: "cpu",
        header: "CPU CORES",
        accessorKey: "cpu",
        enableSorting: true,
        cell: ({ row }) => (
          <CPUColumn
            cores={row.original.kvm.resources.cores}
            overCommit={row.original.kvm.cpu_over_commit_ratio}
          />
        ),
      },
      {
        id: "ram",
        header: "RAM",
        accessorKey: "ram",
        enableSorting: true,
        cell: ({ row }) => (
          <RAMColumn
            memory={row.original.kvm.resources.memory}
            overCommit={row.original.kvm.memory_over_commit_ratio}
          />
        ),
      },
      {
        id: "storage",
        header: "STORAGE",
        accessorKey: "storage",
        enableSorting: true,
        cell: ({ row }) => (
          <StorageColumn
            pools={row.original.kvm.resources.storage_pools}
            storage={row.original.kvm.resources.storage}
          />
        ),
      },
    ],
    []
  );
};
export default useVirshTableColumns;
