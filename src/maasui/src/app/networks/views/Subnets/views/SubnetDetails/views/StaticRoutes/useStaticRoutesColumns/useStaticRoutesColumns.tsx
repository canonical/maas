import { useMemo } from "react";

import type { ColumnDef, Row } from "@tanstack/react-table";

import DeleteStaticRouteForm from "../DeleteStaticRouteform";
import EditStaticRouteForm from "../EditStaticRouteForm";

import SubnetLink from "@/app/base/components/SubnetLink";
import TableActions from "@/app/base/components/TableActions";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { StaticRoute } from "@/app/store/staticroute/types";

export type StaticRouteColumnDef = ColumnDef<StaticRoute, Partial<StaticRoute>>;

const useStaticRoutesColumns = (): StaticRouteColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  return useMemo(
    () => [
      {
        id: "gateway_ip",
        accessorKey: "gateway_ip",
        enableSorting: true,
        header: "Gateway IP",
      },
      {
        id: "destination",
        accessorKey: "destination",
        enableSorting: true,
        header: "Destination",
        cell: ({
          row: {
            original: { destination },
          },
        }: {
          row: Row<StaticRoute>;
        }) => <SubnetLink id={destination} />,
      },
      {
        id: "metric",
        accessorKey: "metric",
        enableSorting: true,
        header: "Metric",
      },
      {
        id: "actions",
        accessorKey: "id",
        enableSorting: false,
        header: "Actions",
        cell: ({
          row: {
            original: { id },
          },
        }: {
          row: Row<StaticRoute>;
        }) => (
          <TableActions
            onDelete={() => {
              openSidePanel({
                component: DeleteStaticRouteForm,
                title: "Delete static route",
                props: {
                  staticRouteId: id,
                },
              });
            }}
            onEdit={() => {
              openSidePanel({
                component: EditStaticRouteForm,
                title: "Edit static route",
                props: {
                  staticRouteId: id,
                },
              });
            }}
          />
        ),
      },
    ],
    [openSidePanel]
  );
};

export default useStaticRoutesColumns;
