import { useMemo } from "react";

import { Icon } from "@canonical/react-components";
import type { ColumnDef } from "@tanstack/react-table";

import DoubleRow from "@/app/base/components/DoubleRow";
import DiskNumaNodes from "@/app/base/components/node/DiskNumaNodes";
import type { Disk } from "@/app/store/types/node";

export type CloneStorage = {
  id: string;
  name: string;
  model: string;
  firmwareVersion: string;
  type: string;
  numaNodesDisk: Disk;
  size: string;
  available: boolean;
};

export type CloneStorageColumnDef = ColumnDef<
  CloneStorage,
  Partial<CloneStorage>
>;

const useCloneStorageTableColumns = (): CloneStorageColumnDef[] => {
  return useMemo(
    (): CloneStorageColumnDef[] => [
      {
        id: "name",
        accessorKey: "name",
        enableSorting: false,
        header: () => <span className="name-col">Name</span>,
        cell: ({
          row: {
            original: { name },
          },
        }) => <DoubleRow primary={name} primaryTitle={name} />,
      },
      {
        id: "model",
        accessorKey: "model",
        enableSorting: false,
        header: () => (
          <span className="model-col">
            <div>Model</div>
            <div>Firmware</div>
          </span>
        ),
        cell: ({
          row: {
            original: { model, firmwareVersion },
          },
        }) => (
          <DoubleRow
            primary={model}
            primaryTitle={model}
            secondary={firmwareVersion}
            secondaryTitle={firmwareVersion}
          />
        ),
      },
      {
        id: "type",
        accessorKey: "type",
        enableSorting: false,
        header: () => (
          <span className="type-col">
            <div>Type</div>
            <div>NUMA node</div>
          </span>
        ),
        cell: ({
          row: {
            original: { type, numaNodesDisk },
          },
        }) => (
          <DoubleRow
            primary={type}
            primaryTitle={type}
            secondary={<DiskNumaNodes disk={numaNodesDisk} />}
          />
        ),
      },
      {
        id: "size",
        accessorKey: "size",
        enableSorting: false,
        header: () => <span className="size-col">Size</span>,
        cell: ({
          row: {
            original: { size },
          },
        }) => <>{size}</>,
      },
      {
        id: "available",
        accessorKey: "available",
        enableSorting: false,
        header: () => (
          <span className="available-col u-align--center">Available</span>
        ),
        cell: ({
          row: {
            original: { available },
          },
        }) => (
          <Icon
            aria-label={available ? "available" : "not available"}
            name={available ? "tick" : "close"}
          />
        ),
      },
    ],
    []
  );
};

export default useCloneStorageTableColumns;
