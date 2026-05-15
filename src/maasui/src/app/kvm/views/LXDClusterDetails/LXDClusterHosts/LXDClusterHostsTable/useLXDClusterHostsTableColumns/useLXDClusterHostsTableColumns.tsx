import { useMemo } from "react";

import { Button, Icon } from "@canonical/react-components";
import type { ColumnDef, Row } from "@tanstack/react-table";
import { Link, useLocation } from "react-router";

import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";
import CPUColumn from "@/app/kvm/components/CPUColumn";
import ComposeForm from "@/app/kvm/components/ComposeForm";
import NameColumn from "@/app/kvm/components/NameColumn";
import RAMColumn from "@/app/kvm/components/RAMColumn";
import StorageColumn from "@/app/kvm/components/StorageColumn";
import TagsColumn from "@/app/kvm/components/TagsColumn";
import type { LXDClusterHost } from "@/app/kvm/views/LXDClusterDetails/LXDClusterHosts/LXDClusterHostsTable/LXDClusterHostsTable";

type LxdKVMClusterHostColumnDef = ColumnDef<
  LXDClusterHost,
  Partial<LXDClusterHost>
>;

export const useLXDClusterHostsTableColumns = ({
  clusterId,
}: {
  clusterId: number;
}): LxdKVMClusterHostColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  const location = useLocation();

  return useMemo(
    () =>
      [
        {
          id: "name",
          accessorKey: "name",
          enableSorting: true,
          header: () => (
            <div>
              <div>KVM host</div>
              <div>Address</div>
            </div>
          ),
          cell: ({
            row: {
              original: { id, name, power_parameters },
            },
          }: {
            row: Row<LXDClusterHost>;
          }) => {
            return (
              <NameColumn
                name={name}
                secondary={power_parameters?.power_address}
                url={urls.kvm.lxd.cluster.vms.host({
                  clusterId,
                  hostId: id,
                })}
              />
            );
          },
        },
        {
          id: "vms",
          accessorKey: "vms",
          enableSorting: true,
          header: "VMs",
          cell: ({
            row: {
              original: { vms },
            },
          }: {
            row: Row<LXDClusterHost>;
          }) => {
            return vms;
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
            row: Row<LXDClusterHost>;
          }) => {
            return tags ? <TagsColumn tags={tags} /> : null;
          },
        },
        {
          id: "pool",
          accessorKey: "poolName",
          enableSorting: true,
          header: "Resource pool",
          cell: ({
            row: {
              original: { poolName },
            },
          }: {
            row: Row<LXDClusterHost>;
          }) => {
            return <span data-testid="host-pool-name">{poolName}</span>;
          },
        },
        {
          id: "cpuAllocated",
          accessorKey: "cpuAllocated",
          enableSorting: true,
          header: "CPU cores",
          cell: ({
            row: {
              original: { resources, cpu_over_commit_ratio },
            },
          }: {
            row: Row<LXDClusterHost>;
          }) => {
            return (
              <CPUColumn
                cores={resources.cores}
                overCommit={cpu_over_commit_ratio}
              />
            );
          },
        },
        {
          id: "ramAllocated",
          accessorKey: "ramAllocated",
          enableSorting: true,
          header: "RAM",
          cell: ({
            row: {
              original: { resources, memory_over_commit_ratio },
            },
          }: {
            row: Row<LXDClusterHost>;
          }) => {
            return (
              <RAMColumn
                memory={resources.memory}
                overCommit={memory_over_commit_ratio}
              />
            );
          },
        },
        {
          id: "storageAllocated",
          accessorKey: "storageAllocated",
          enableSorting: true,
          header: "Storage",
          cell: ({
            row: {
              original: { resources },
            },
          }: {
            row: Row<LXDClusterHost>;
          }) => {
            return (
              <StorageColumn
                pools={resources.storage_pools}
                storage={resources.storage}
              />
            );
          },
        },
        {
          id: "actions",
          accessorKey: "id",
          enableSorting: false,
          header: "Actions",
          cell: ({
            row: {
              original: { id },
            },
          }: {
            row: Row<LXDClusterHost>;
          }) => {
            return (
              <div>
                <Button
                  appearance="base"
                  className="is-dense u-table-cell-padding-overlap u-no-margin--right"
                  data-testid="vm-host-compose"
                  hasIcon
                  onClick={() => {
                    openSidePanel({
                      component: ComposeForm,
                      title: "Compose",
                      props: {
                        hostId: id,
                      },
                    });
                  }}
                >
                  <Icon name="plus" />
                </Button>
                <Link
                  className="is-dense no-background has-icon u-no-margin u-table-cell-padding-overlap"
                  data-testid="vm-host-settings"
                  state={{ from: location.pathname }}
                  to={{
                    pathname: urls.kvm.lxd.cluster.host.edit({
                      clusterId,
                      hostId: id,
                    }),
                  }}
                >
                  <Icon name="settings" />
                </Link>
              </div>
            );
          },
        },
      ] as LxdKVMClusterHostColumnDef[],
    [clusterId, openSidePanel, location.pathname]
  );
};
