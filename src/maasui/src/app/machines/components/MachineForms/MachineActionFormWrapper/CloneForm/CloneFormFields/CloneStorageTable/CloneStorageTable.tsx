import type { ReactElement, RefObject } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import classNames from "classnames";

import type { CloneStorage } from "./useCloneStorageTableColumns/useCloneStorageTableColumns";
import useCloneStorageTableColumns from "./useCloneStorageTableColumns/useCloneStorageTableColumns";

import type { MachineDetails } from "@/app/store/machine/types";
import type { Disk, Partition } from "@/app/store/types/node";
import {
  diskAvailable,
  formatSize,
  formatType,
  partitionAvailable,
} from "@/app/store/utils";

type CloneStorageTableProps = {
  containerRef?: RefObject<HTMLElement | null>;
  loadingMachineDetails?: boolean;
  machine: MachineDetails | null;
  selected: boolean;
};

export const CloneStorageTable = ({
  containerRef,
  loadingMachineDetails = false,
  machine,
  selected,
}: CloneStorageTableProps): ReactElement => {
  const columns = useCloneStorageTableColumns();
  const data: CloneStorage[] = [];

  if (machine) {
    machine.disks.forEach((disk: Disk) => {
      data.push({
        id: `disk-${disk.id}`,
        name: disk.name,
        model: disk.model || "—",
        firmwareVersion: disk.firmware_version,
        type: formatType(disk),
        numaNodesDisk: disk,
        size: formatSize(disk.size),
        available: diskAvailable(disk),
      });

      if (disk.partitions) {
        disk.partitions.forEach((partition: Partition) => {
          data.push({
            id: `partition-${partition.id}`,
            name: partition.name,
            model: "—",
            firmwareVersion: "",
            type: formatType(partition),
            numaNodesDisk: disk,
            size: formatSize(partition.size),
            available: partitionAvailable(partition),
          });
        });
      }
    });
  }

  return (
    <GenericTable
      aria-label="Clone storage"
      className={classNames("clone-table--storage", {
        "not-selected": !selected,
      })}
      columns={columns}
      containerRef={containerRef}
      data={data}
      isLoading={loadingMachineDetails}
      noData={machine ? "No storage information detected." : null}
      variant="full-height"
    />
  );
};

export default CloneStorageTable;
