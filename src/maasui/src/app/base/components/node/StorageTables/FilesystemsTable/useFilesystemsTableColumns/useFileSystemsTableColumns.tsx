import { useMemo } from "react";

import type { ColumnDef, Row } from "@tanstack/react-table";

import TableMenu from "@/app/base/components/TableMenu";
import DeleteFilesystem from "@/app/base/components/node/StorageTables/FilesystemsTable/DeleteFilesystem";
import DeleteSpecialFilesystem from "@/app/base/components/node/StorageTables/FilesystemsTable/DeleteSpecialFilesystem";
import type { FilesystemRow } from "@/app/base/components/node/StorageTables/FilesystemsTable/FilesystemsTable";
import UnmountFilesystem from "@/app/base/components/node/StorageTables/FilesystemsTable/UnmountFilesystem";
import { useSidePanel } from "@/app/base/side-panel-context";
import { formatSize, usesStorage } from "@/app/store/utils";

export type FilesystemsColumnDef = ColumnDef<
  FilesystemRow,
  Partial<FilesystemRow>
>;

const useFileSystemsTableColumns = (
  canEditStorage: boolean,
  isMachine: boolean
): FilesystemsColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  return useMemo(
    () =>
      [
        {
          id: "name",
          accessorKey: "name",
          enableSorting: false,
          header: "Name",
          cell: ({
            row: {
              original: { name },
            },
          }: {
            row: Row<FilesystemRow>;
          }) => name ?? "—",
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
            row: Row<FilesystemRow>;
          }) => (size ? formatSize(size) : "—"),
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
        {
          id: "mountOptions",
          accessorKey: "mount_options",
          enableSorting: false,
          header: "Mount options",
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
                    original: { fstype, mount_point, node, storage },
                  },
                }: {
                  row: Row<FilesystemRow>;
                }) => {
                  const links = [];
                  if (usesStorage(fstype) && storage) {
                    links.push({
                      children: "Unmount filesystem...",
                      onClick: () => {
                        openSidePanel({
                          component: UnmountFilesystem,
                          title: "Unmount filesystem",
                          props: {
                            systemId: node.system_id,
                            storageDevice: storage,
                          },
                        });
                      },
                    });
                  }
                  links.push({
                    children: "Remove filesystem...",
                    onClick: () => {
                      if (node.special_filesystems && !storage) {
                        openSidePanel({
                          component: DeleteSpecialFilesystem,
                          title: "Remove special filesystem",
                          props: {
                            systemId: node.system_id,
                            mountPoint: mount_point,
                          },
                        });
                      } else if (storage) {
                        openSidePanel({
                          component: DeleteFilesystem,
                          title: "Remove filesystem",
                          props: {
                            systemId: node.system_id,
                            storageDevice: storage,
                          },
                        });
                      }
                    },
                  });
                  return (
                    <TableMenu
                      disabled={!canEditStorage}
                      links={links}
                      position="right"
                      title="Take action:"
                    />
                  );
                },
              },
            ]
          : []),
      ] as FilesystemsColumnDef[],
    [canEditStorage, isMachine, openSidePanel]
  );
};

export default useFileSystemsTableColumns;
