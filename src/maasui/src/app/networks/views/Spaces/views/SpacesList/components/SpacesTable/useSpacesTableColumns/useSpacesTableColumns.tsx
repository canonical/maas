import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";
import { Link } from "react-router";

import type { SpaceResponse } from "@/app/apiclient";
import TableActions from "@/app/base/components/TableActions";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/networks/urls";
import { DeleteSpace } from "@/app/networks/views/Spaces/components";

type SpacesColumnDef = ColumnDef<SpaceResponse, Partial<SpaceResponse>>;

const useSpacesTableColumns = (): SpacesColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  return useMemo<SpacesColumnDef[]>(
    () => [
      {
        id: "name",
        accessorKey: "name",
        enableSorting: true,
        cell: ({
          row: {
            original: { id, name },
          },
        }) => <Link to={urls.space.index({ id })}>{name}</Link>,
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
                component: DeleteSpace,
                title: "Delete space",
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

export default useSpacesTableColumns;
