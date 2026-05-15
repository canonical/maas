import { useMemo } from "react";

import type { ColumnDef, Row } from "@tanstack/react-table";

import TableMenu from "@/app/base/components/TableMenu";
import DeleteCacheSet from "@/app/base/components/node/StorageTables/AvailableStorageTable/DeleteCacheSet";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { Disk, Node } from "@/app/store/types/node";
import { formatSize } from "@/app/store/utils";

export type CacheSetsColumnDef = ColumnDef<Disk, Partial<Disk>>;

type Props = {
  isMachine: boolean;
  canEditStorage: boolean;
  systemId: Node["system_id"];
};

const useCacheSetsColumns = ({
  isMachine,
  canEditStorage,
  systemId,
}: Props): CacheSetsColumnDef[] => {
  const { openSidePanel } = useSidePanel();

  return useMemo<CacheSetsColumnDef[]>(
    () => [
      {
        id: "name",
        accessorKey: "name",
        enableSorting: false,
      },
      {
        id: "size",
        accessorKey: "size",
        enableSorting: false,
        cell: ({ row: { original: disk } }) => formatSize(disk.size),
      },
      {
        id: "used_for",
        accessorKey: "used_for",
        enableSorting: false,
        header: "Used for",
      },
      ...(isMachine
        ? [
            {
              id: "actions",
              accessorKey: "actions",
              enableSorting: false,
              cell: ({ row: { original: disk } }: { row: Row<Disk> }) => (
                <TableMenu
                  disabled={!canEditStorage}
                  links={[
                    {
                      children: "Remove cache set...",
                      onClick: () => {
                        openSidePanel({
                          component: DeleteCacheSet,
                          title: "Remove cache set",
                          props: {
                            systemId,
                            disk,
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
    ],
    [canEditStorage, isMachine, openSidePanel, systemId]
  );
};

export default useCacheSetsColumns;
