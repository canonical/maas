import { useMemo } from "react";

import { Icon, Input } from "@canonical/react-components";
import type { ColumnDef, Row } from "@tanstack/react-table";

import type { Disk, Partition } from "@/app/store/types/node";
import { formatSize, formatType } from "@/app/store/utils";

type StorageDeviceWithSpare = { isSpare?: boolean } & (Disk | Partition);

export type DatastoreColumnDef = ColumnDef<
  StorageDeviceWithSpare,
  Partial<StorageDeviceWithSpare>
>;

const useDatastoreTableColumns = ({
  maxSpares,
  numSpares,
  handleSpareCheckbox,
}: {
  maxSpares: number;
  numSpares: number;
  handleSpareCheckbox?: (
    storageDevice: Disk | Partition,
    isSpareDevice: boolean
  ) => void;
}): DatastoreColumnDef[] => {
  return useMemo(
    () =>
      [
        {
          id: "name",
          accessorKey: "name",
          enableSorting: false,
          header: () => "Name",
        },
        {
          id: "size",
          accessorKey: "size",
          enableSorting: false,
          header: () => "Size",
          cell: ({
            row: {
              original: { size },
            },
          }: {
            row: Row<Disk | Partition>;
          }) => formatSize(size),
        },
        {
          id: "type",
          accessorKey: "type",
          enableSorting: false,
          header: () => "Device type",
          cell: ({
            row: { original: device },
          }: {
            row: Row<Disk | Partition>;
          }) => formatType(device),
        },
        ...(maxSpares > 0
          ? [
              {
                id: "active",
                accessorKey: "active",
                enableSorting: false,
                header: () => "Active",
                cell: ({
                  row: { original: device },
                }: {
                  row: Row<StorageDeviceWithSpare>;
                }) => {
                  const isSpareDevice = device.isSpare;
                  return (
                    <div data-testid="active-status">
                      {isSpareDevice ? (
                        <Icon data-testid="is-spare" name="close" />
                      ) : (
                        <Icon data-testid="is-active" name="tick" />
                      )}
                    </div>
                  );
                },
              },
              {
                id: "max-spares",
                accessorKey: "max-spares",
                enableSorting: false,
                header: () => `Spare (max ${maxSpares})`,
                cell: ({
                  row: { original: device },
                }: {
                  row: Row<StorageDeviceWithSpare>;
                  table: {
                    getRowModel: () => {
                      rows: { original: StorageDeviceWithSpare }[];
                    };
                  };
                }) => {
                  const isSpareDevice = device.isSpare;
                  return (
                    <Input
                      checked={isSpareDevice}
                      data-testid={`raid-${device.type}-${device.id}`}
                      disabled={!isSpareDevice && numSpares >= maxSpares}
                      id={`raid-${device.type}-${device.id}`}
                      label=" "
                      labelClassName="is-inline-label"
                      onChange={() => {
                        if (handleSpareCheckbox) {
                          handleSpareCheckbox(device, isSpareDevice ?? false);
                        }
                      }}
                      type="checkbox"
                    />
                  );
                },
              },
            ]
          : []),
      ] as DatastoreColumnDef[],
    [handleSpareCheckbox, maxSpares, numSpares]
  );
};

export default useDatastoreTableColumns;
