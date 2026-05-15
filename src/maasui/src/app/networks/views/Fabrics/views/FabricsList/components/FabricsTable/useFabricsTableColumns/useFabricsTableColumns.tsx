import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";
import { Link } from "react-router";

import type { FabricResponse } from "@/app/apiclient";
import TableActions from "@/app/base/components/TableActions";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/networks/urls";
import { DeleteFabric } from "@/app/networks/views/Fabrics/components";

type FabricsColumnDef = ColumnDef<FabricResponse, Partial<FabricResponse>>;

const useFabricsTableColumns = (): FabricsColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  return useMemo<FabricsColumnDef[]>(
    () => [
      {
        id: "name",
        accessorKey: "name",
        enableSorting: true,
        cell: ({
          row: {
            original: { id, name },
          },
        }) => <Link to={urls.fabric.index({ id })}>{name}</Link>,
      },
      {
        id: "description",
        accessorKey: "description",
      },
      {
        id: "actions",
        header: "Actions",
        cell: ({
          row: {
            original: { id },
          },
        }) => (
          <TableActions
            onDelete={() => {
              openSidePanel({
                component: DeleteFabric,
                title: "Delete fabric",
                props: { id },
              });
            }}
          />
        ),
      },
    ],
    [openSidePanel]
  );
};

export default useFabricsTableColumns;
