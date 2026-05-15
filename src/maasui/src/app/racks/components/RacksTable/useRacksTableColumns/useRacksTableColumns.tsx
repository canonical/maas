import { useMemo } from "react";

import type { ColumnDef, Row } from "@tanstack/react-table";
import pluralize from "pluralize";
import { Link } from "react-router";

import DeleteRack from "../../DeleteRack";
import EditRack from "../../EditRack";
import RegisterController from "../../RegisterController";
import RemoveControllers from "../../RemoveControllers";

import type { RackWithSummaryResponse } from "@/app/apiclient";
import TableMenu from "@/app/base/components/TableMenu";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";
import { FilterControllers } from "@/app/store/controller/utils";

type RacksColumnDef = ColumnDef<RackWithSummaryResponse>;

const getControllersLabel = (row: Row<RackWithSummaryResponse>) => {
  if (row.original.registered_agents_system_ids.length === 0) {
    return "0 controllers";
  }
  const filters = FilterControllers.filtersToQueryString({
    system_id: [`=${row.original.registered_agents_system_ids.join(",")}`],
  });
  return (
    <Link to={`${urls.controllers.index}${filters}`}>
      {`${row.original.registered_agents_system_ids.length} ${pluralize("controller", row.original.registered_agents_system_ids.length)}`}
    </Link>
  );
};

const useRacksTableColumns = (): RacksColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  return useMemo(
    () => [
      {
        id: "name",
        accessorKey: "name",
        enableSorting: true,
        header: "Name",
      },
      {
        id: "registered",
        accessorKey: "registered_agents_system_ids",
        enableSorting: true,
        header: "Registered",
        cell: ({ row }) => {
          return getControllersLabel(row);
        },
      },
      {
        id: "actions",
        accessorKey: "id",
        enableSorting: false,
        header: "Actions",
        //TODO Correctly disable actions when backend is ready
        cell: ({ row }) => {
          return (
            <TableMenu
              links={[
                {
                  children: "Edit rack...",
                  onClick: () => {
                    openSidePanel({
                      component: EditRack,
                      title: "Edit rack",
                      props: { id: row.original.id },
                    });
                  },
                },
                {
                  children: "Delete rack...",
                  onClick: () => {
                    openSidePanel({
                      component: DeleteRack,
                      title: "Delete rack",
                      props: {
                        id: row.original.id,
                      },
                    });
                  },
                },
                {
                  children: "Register controller...",
                  onClick: () => {
                    openSidePanel({
                      component: RegisterController,
                      title: "Register controller",
                      props: {
                        id: row.original.id,
                      },
                    });
                  },
                },
                {
                  children: "Remove controllers...",
                  onClick: () => {
                    openSidePanel({
                      component: RemoveControllers,
                      title: "Remove controllers",
                      props: {
                        id: row.original.id,
                      },
                    });
                  },
                },
              ]}
              position="right"
              title="Take action:"
            />
          );
        },
      },
    ],
    [openSidePanel]
  );
};

export default useRacksTableColumns;
