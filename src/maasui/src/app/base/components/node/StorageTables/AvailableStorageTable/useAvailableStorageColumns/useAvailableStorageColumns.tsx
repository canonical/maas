import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";
import { useSelector } from "react-redux";

import DiskBootStatus from "../../../DiskBootStatus";
import DiskNumaNodes from "../../../DiskNumaNodes";
import DiskTestStatus from "../../../DiskTestStatus";
import AddLogicalVolume from "../AddLogicalVolume";
import AddPartition from "../AddPartition";
import CreateBcache from "../CreateBcache";
import CreateCacheSet from "../CreateCacheSet";
import DeleteDisk from "../DeleteDisk";
import DeletePartition from "../DeletePartition";
import DeleteVolumeGroup from "../DeleteVolumeGroup";
import EditDisk from "../EditDisk";
import EditPartition from "../EditPartition";
import SetBootDisk from "../SetBootDisk";

import DoubleRow from "@/app/base/components/DoubleRow";
import TableMenu from "@/app/base/components/TableMenu";
import TagLinks from "@/app/base/components/TagLinks";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";
import { FilterControllers } from "@/app/store/controller/utils";
import machineSelectors from "@/app/store/machine/selectors";
import { FilterMachines, isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import type { Disk, Node, Partition } from "@/app/store/types/node";
import {
  canBeDeleted,
  canBePartitioned,
  canCreateBcache,
  canCreateCacheSet,
  canCreateLogicalVolume,
  canSetBootDisk,
  formatSize,
  formatType,
  isDisk,
  isPartition,
  isVolumeGroup,
} from "@/app/store/utils";

export type AvailableStorageRow = Disk | (Partition & { parentDisk?: Disk });
type AvailableStorageColumnDef = ColumnDef<AvailableStorageRow>;

const useAvailableStorageColumns = ({
  isMachine,
  actionsDisabled,
  systemId,
}: {
  isMachine: boolean;
  actionsDisabled: boolean;
  systemId: Node["system_id"];
}): AvailableStorageColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );

  return useMemo(
    (): AvailableStorageColumnDef[] => [
      {
        id: "name",
        accessorKey: "name",
        enableSorting: false,
        header: () => (
          <div>
            <div>Name</div>
            <div>Serial</div>
          </div>
        ),
        cell: ({ row: { original: disk } }) => (
          <DoubleRow
            primary={disk.name}
            primaryTitle={disk.name}
            secondary={"serial" in disk && disk.serial}
            secondaryClassName={isMachine ? "u-nudge--secondary-row" : null}
            secondaryTitle={"serial" in disk ? disk.serial : null}
          />
        ),
      },
      {
        id: "model",
        accessorKey: "model",
        enableSorting: false,
        header: () => (
          <div>
            <div>Model</div>
            <div>Firmware</div>
          </div>
        ),
        cell: ({ row: { original: disk } }) => (
          <DoubleRow
            primary={"model" in disk ? disk.model : "—"}
            primaryTitle={"model" in disk ? disk.model : null}
            secondary={"firmware_version" in disk && disk.firmware_version}
            secondaryTitle={
              "firmware_version" in disk ? disk.firmware_version : null
            }
          />
        ),
      },
      {
        id: "is_boot",
        accessorKey: "is_boot",
        enableSorting: false,
        header: "Boot",
        cell: ({ row: { original: disk } }) => (
          <DoubleRow
            primary={"is_boot" in disk ? <DiskBootStatus disk={disk} /> : "—"}
          />
        ),
      },
      {
        id: "size",
        accessorKey: "size",
        enableSorting: false,
        header: "Size",
        cell: ({ row: { original: disk } }) => (
          <DoubleRow
            primary={formatSize(disk.size)}
            secondary={
              "available_size" in disk &&
              `Free: ${formatSize(disk.available_size)}`
            }
          />
        ),
      },
      {
        id: "type",
        accessorKey: "type",
        enableSorting: false,
        header: () => (
          <div>
            <div>Type</div>
            <div>NUMA node</div>
          </div>
        ),
        cell: ({ row: { original: disk } }) => (
          <DoubleRow
            primary={formatType(disk)}
            secondary={
              ("numa_node" in disk || "numa_nodes" in disk) && (
                <DiskNumaNodes disk={disk} />
              )
            }
          />
        ),
      },
      {
        id: "health",
        accessorKey: "health",
        enableSorting: false,
        header: () => (
          <div>
            <div>Health</div>
            <div>Tags</div>
          </div>
        ),
        cell: ({ row: { original: disk } }) => (
          <DoubleRow
            primary={
              "test_status" in disk ? (
                <DiskTestStatus testStatus={disk.test_status} />
              ) : (
                "—"
              )
            }
            secondary={
              <TagLinks
                getLinkURL={(tag) => {
                  if (isMachine) {
                    const filter = FilterMachines.filtersToQueryString({
                      storage_tags: [`=${tag}`],
                    });
                    return `${urls.machines.index}${filter}`;
                  }
                  const filter = FilterControllers.filtersToQueryString({
                    storage_tags: [`=${tag}`],
                  });
                  return `${urls.controllers.index}${filter}`;
                }}
                tags={disk.tags}
              />
            }
          />
        ),
      },
      ...(isMachine
        ? [
            {
              id: "actions",
              accessorKey: "id",
              enableSorting: false,
              header: "Actions",
              cell: ({
                row: { original: disk },
              }: {
                row: { original: AvailableStorageRow };
              }) => {
                if (!isMachineDetails(machine)) return null;

                const links: {
                  children: string;
                  onClick: () => void;
                }[] = [];

                if (isDisk(disk)) {
                  if (canCreateLogicalVolume(disk)) {
                    links.push({
                      children: "Add logical volume...",
                      onClick: () => {
                        openSidePanel({
                          component: AddLogicalVolume,
                          title: "Add logical volume",
                          props: {
                            systemId,
                            disk: disk as Disk,
                          },
                        });
                      },
                    });
                  }
                  if (canBePartitioned(disk)) {
                    links.push({
                      children: "Add partition...",
                      onClick: () => {
                        openSidePanel({
                          component: AddPartition,
                          title: "Add partition",
                          props: {
                            systemId,
                            disk: disk as Disk,
                          },
                        });
                      },
                    });
                  }
                  if (canCreateBcache(machine.disks, disk)) {
                    links.push({
                      children: "Create bcache...",
                      onClick: () => {
                        openSidePanel({
                          component: CreateBcache,
                          title: "Create bcache",
                          props: {
                            systemId,
                            storageDevice: disk as Disk | Partition,
                          },
                        });
                      },
                    });
                  }
                  if (canCreateCacheSet(disk)) {
                    links.push({
                      children: "Create cache set...",
                      onClick: () => {
                        openSidePanel({
                          component: CreateCacheSet,
                          title: "Create cache set",
                          props: {
                            systemId,
                            diskId: (disk as Disk).id,
                            partitionId: undefined,
                          },
                        });
                      },
                    });
                  }
                  if (canSetBootDisk(machine.detected_storage_layout, disk)) {
                    links.push({
                      children: "Set boot disk...",
                      onClick: () => {
                        openSidePanel({
                          component: SetBootDisk,
                          title: "Set boot disk",
                          props: {
                            systemId,
                            diskId: (disk as Disk).id,
                          },
                        });
                      },
                    });
                  }
                  if (!isVolumeGroup(disk)) {
                    links.push({
                      children: `Edit ${formatType(disk, true)}...`,
                      onClick: () => {
                        openSidePanel({
                          component: EditDisk,
                          title: `Edit ${formatType(disk, true)}`,
                          props: {
                            systemId,
                            disk: disk as Disk,
                          },
                        });
                      },
                    });
                  }
                  if (canBeDeleted(disk) && isVolumeGroup(disk)) {
                    links.push({
                      children: "Remove volume group...",
                      onClick: () => {
                        openSidePanel({
                          component: DeleteVolumeGroup,
                          title: "Remove volume group",
                          props: {
                            systemId,
                            diskId: (disk as Disk).id,
                          },
                        });
                      },
                    });
                  }
                  if (canBeDeleted(disk) && !isVolumeGroup(disk)) {
                    links.push({
                      children: `Remove ${formatType(disk, true)}...`,
                      onClick: () => {
                        openSidePanel({
                          component: DeleteDisk,
                          title: `Remove ${formatType(disk, true)}`,
                          props: {
                            systemId,
                            disk: disk as Disk,
                          },
                        });
                      },
                    });
                  }
                }
                if (isPartition(disk)) {
                  const partition = disk as Partition & { parentDisk?: Disk };
                  links.push({
                    children: "Edit partition...",
                    onClick: () => {
                      openSidePanel({
                        component: EditPartition,
                        title: "Edit partition",
                        props: {
                          systemId,
                          partition: partition as Partition,
                          disk: partition.parentDisk as Disk,
                        },
                      });
                    },
                  });
                  if (canCreateBcache(machine.disks, disk)) {
                    links.push({
                      children: "Create bcache...",
                      onClick: () => {
                        openSidePanel({
                          component: CreateBcache,
                          title: "Create bcache",
                          props: {
                            systemId,
                            storageDevice: partition as Disk | Partition,
                          },
                        });
                      },
                    });
                  }
                  if (canCreateCacheSet(disk)) {
                    links.push({
                      children: "Create cache set...",
                      onClick: () => {
                        openSidePanel({
                          component: CreateCacheSet,
                          title: "Create cache set",
                          props: {
                            systemId,
                            diskId: undefined,
                            partitionId: partition.id,
                          },
                        });
                      },
                    });
                  }
                  links.push({
                    children: "Remove partition...",
                    onClick: () => {
                      openSidePanel({
                        component: DeletePartition,
                        title: "Remove partition",
                        props: {
                          systemId,
                          partitionId: partition.id,
                        },
                      });
                    },
                  });
                }

                return (
                  <TableMenu
                    disabled={actionsDisabled}
                    links={links}
                    position="right"
                    title="Take action:"
                  />
                );
              },
            },
          ]
        : []),
    ],
    [actionsDisabled, isMachine, openSidePanel, systemId, machine]
  );
};

export default useAvailableStorageColumns;
