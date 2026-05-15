import { useMemo } from "react";

import { Icon } from "@canonical/react-components";
import type { ColumnDef, Row } from "@tanstack/react-table";
import pluralize from "pluralize";

import DoubleRow from "@/app/base/components/DoubleRow";
import CPUColumn from "@/app/kvm/components/CPUColumn";
import NameColumn from "@/app/kvm/components/NameColumn";
import PoolColumn from "@/app/kvm/components/PoolColumn";
import RAMColumn from "@/app/kvm/components/RAMColumn";
import StorageColumn from "@/app/kvm/components/StorageColumn";
import TagsColumn from "@/app/kvm/components/TagsColumn";
import VMsColumn from "@/app/kvm/components/VMsColumn";
import type { LXDKVMHost } from "@/app/kvm/views/KVMList/LXDHostsTable/LXDHostsTable";
import { LxdKVMHostType } from "@/app/kvm/views/KVMList/LXDHostsTable/LXDHostsTable";

type LxdKVMHostColumnDef = ColumnDef<LXDKVMHost, Partial<LXDKVMHost>>;

export const useLXDHostsTableColumns = (): LxdKVMHostColumnDef[] => {
  return useMemo(
    () =>
      [
        {
          id: "name",
          accessorKey: "name",
          enableSorting: true,
          header: () => (
            <div>
              <div>Name</div>
              <div>Project</div>
            </div>
          ),
          cell: ({
            row: {
              original: { name, project, url },
            },
          }: {
            row: Row<LXDKVMHost>;
          }) => {
            return <NameColumn name={name} secondary={project} url={url} />;
          },
        },
        {
          id: "hostType",
          accessorKey: "hostType",
          enableSorting: true,
          header: "KVM host type",
          cell: ({
            row: {
              original: { hostsCount, hostType },
            },
          }: {
            row: Row<LXDKVMHost>;
          }) => {
            const isCluster = hostType === LxdKVMHostType.Cluster;
            return (
              <DoubleRow
                icon={<Icon name={isCluster ? "cluster" : "single-host"} />}
                primary={
                  <span data-testid="host-type">
                    {isCluster ? "Cluster" : "Single host"}
                  </span>
                }
                secondary={
                  isCluster ? (
                    <span data-testid="hosts-count">
                      {pluralize("KVM host", hostsCount, true)}
                    </span>
                  ) : null
                }
              />
            );
          },
        },
        {
          id: "vms",
          accessorKey: "vms",
          enableSorting: true,
          header: () => (
            <>
              <span>VMs</span>
              <br />
              <span>LXD version</span>
            </>
          ),
          cell: ({
            row: {
              original: { version, vms },
            },
          }: {
            row: Row<LXDKVMHost>;
          }) => {
            return <VMsColumn version={version} vms={vms} />;
          },
        },
        {
          id: "tags",
          accessorKey: "tags",
          enableSorting: true,
          header: "Tags",
          cell: ({
            row: {
              original: { tags },
            },
          }: {
            row: Row<LXDKVMHost>;
          }) => {
            return tags ? <TagsColumn tags={tags} /> : null;
          },
        },
        {
          id: "zone",
          accessorKey: "zoneName",
          enableSorting: true,
          header: () => (
            <div>
              <div>AZ</div>
              <div>Resource pool</div>
            </div>
          ),
          cell: ({
            row: {
              original: { pool, zone },
            },
          }: {
            row: Row<LXDKVMHost>;
          }) => {
            return pool || pool === 0 || zone || zone === 0 ? (
              <PoolColumn poolId={pool} zoneId={zone} />
            ) : null;
          },
        },
        {
          id: "cpu",
          accessorKey: "cpuAllocated",
          enableSorting: true,
          header: "CPU cores",
          cell: ({
            row: {
              original: { cpuCores, cpuOverCommit },
            },
          }: {
            row: Row<LXDKVMHost>;
          }) => {
            return <CPUColumn cores={cpuCores} overCommit={cpuOverCommit} />;
          },
        },
        {
          id: "ram",
          accessorKey: "ramAllocated",
          enableSorting: true,
          header: "RAM",
          cell: ({
            row: {
              original: { memory, memoryOverCommit },
            },
          }: {
            row: Row<LXDKVMHost>;
          }) => {
            return <RAMColumn memory={memory} overCommit={memoryOverCommit} />;
          },
        },
        {
          id: "storage",
          accessorKey: "storageAllocated",
          enableSorting: true,
          header: "Storage",
          cell: ({
            row: {
              original: { defaultPoolId, storagePools, storage },
            },
          }: {
            row: Row<LXDKVMHost>;
          }) => {
            return (
              <StorageColumn
                defaultPoolId={defaultPoolId}
                pools={storagePools}
                storage={storage}
              />
            );
          },
        },
      ] as LxdKVMHostColumnDef[],
    []
  );
};
