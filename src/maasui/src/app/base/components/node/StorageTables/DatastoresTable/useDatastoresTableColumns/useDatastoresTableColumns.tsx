import { useMemo } from "react";

import type { ColumnDef, Row } from "@tanstack/react-table";

import TableMenu from "@/app/base/components/TableMenu";
import type { DatastoreRow } from "@/app/base/components/node/StorageTables/DatastoresTable/DatastoresTable";
import RemoveDatastore from "@/app/base/components/node/StorageTables/DatastoresTable/RemoveDatastore";
import { useSidePanel } from "@/app/base/side-panel-context";
import { formatSize } from "@/app/store/utils";

export type DatastoresColumnDef = ColumnDef<
  DatastoreRow,
  Partial<DatastoreRow>
>;

const useDatastoresTableColumns = (
  canEditStorage: boolean,
  isMachine: boolean
): DatastoresColumnDef[] => {
  const { openSidePanel } = useSidePanel();

  return useMemo(
    () =>
      [
        {
          id: "name",
          accessorKey: "name",
          enableSorting: false,
          header: "Name",
        },
        {
          id: "size",
          accessorKey: "size",
          enableSorting: false,
          header: "Size",
          cell: ({
            row: {
              original: { size },
            },
          }: {
            row: Row<DatastoreRow>;
          }) => formatSize(size),
        },
        {
          id: "fstype",
          accessorKey: "fstype",
          enableSorting: false,
          header: "Filesystem",
        },
        {
          id: "mountPoint",
          accessorKey: "mount_point",
          enableSorting: false,
          header: "Mount point",
        },
        ...(isMachine
          ? [
              {
                id: "Actions",
                accessorKey: "id",
                enableSorting: false,
                header: "Actions",
                cell: ({
                  row: {
                    original: { disk, systemId },
                  },
                }: {
                  row: Row<DatastoreRow>;
                }) => (
                  <TableMenu
                    disabled={!canEditStorage}
                    links={[
                      {
                        children: "Remove datastore...",
                        onClick: () => {
                          openSidePanel({
                            component: RemoveDatastore,
                            title: "Remove datastore",
                            props: {
                              diskId: disk.id,
                              systemId,
                            },
                          });
                        },
                      },
                    ]}
                    position="right"
                    title="Take action:"
                  />
                ),
              },
            ]
          : []),
      ] as DatastoresColumnDef[],
    [canEditStorage, isMachine, openSidePanel]
  );
};

export default useDatastoresTableColumns;
