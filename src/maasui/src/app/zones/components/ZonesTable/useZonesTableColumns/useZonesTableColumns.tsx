import { useMemo } from "react";

import type { ColumnDef, Row } from "@tanstack/react-table";
import { Link } from "react-router";

import { useGetIsSuperUser } from "@/app/api/query/auth";
import type { ZoneResponse, ZoneWithStatisticsResponse } from "@/app/apiclient";
import TableActions from "@/app/base/components/TableActions";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";
import { FilterDevices } from "@/app/store/device/utils";
import { FilterMachines } from "@/app/store/machine/utils";
import { DeleteZone, EditZone } from "@/app/zones/components";

type ZonesColumnData = ZoneResponse & {
  statistics?: ZoneWithStatisticsResponse;
};

export type ZoneColumnDef = ColumnDef<
  ZonesColumnData,
  Partial<ZonesColumnData>
>;

const filterDevices = (name: string) =>
  FilterDevices.filtersToQueryString({
    zone: [name],
  });

const machinesFilter = (name: string) =>
  FilterMachines.filtersToQueryString({
    zone: [name],
  });

const useZonesTableColumns = (): ZoneColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  const isSuperUser = useGetIsSuperUser();
  return useMemo(
    () => [
      {
        id: "name",
        accessorKey: "name",
        enableSorting: true,
        header: "Name",
      },
      {
        id: "description",
        accessorKey: "description",
        enableSorting: true,
        header: "Description",
      },
      {
        id: "machines_count",
        accessorKey: "machines_count",
        enableSorting: true,
        header: "Machines",
        cell: ({
          row: {
            original: { statistics, name },
          },
        }) => {
          return (
            <Link
              className="u-align--right"
              to={`${urls.machines.index}${machinesFilter(name)}`}
            >
              {statistics?.machines_count}
            </Link>
          );
        },
      },
      {
        id: "devices_count",
        accessorKey: "devices_count",
        enableSorting: true,
        header: "Devices",
        cell: ({
          row: {
            original: { statistics, name },
          },
        }) => {
          return (
            <Link
              className="u-align--right"
              to={`${urls.devices.index}${filterDevices(name)}`}
            >
              {statistics?.devices_count}
            </Link>
          );
        },
      },
      {
        id: "controllers_count",
        accessorKey: "controllers_count",
        enableSorting: true,
        header: "Controllers",
        cell: ({
          row: {
            original: { statistics },
          },
        }) => {
          return (
            <Link className="u-align--right" to={`${urls.controllers.index}`}>
              {statistics?.controllers_count}
            </Link>
          );
        },
      },
      {
        id: "actions",
        accessorKey: "id",
        enableSorting: false,
        header: "Actions",
        cell: ({ row }: { row: Row<ZonesColumnData> }) => {
          const canBeDeleted = isSuperUser.data && row.original.id !== 1;
          return (
            <TableActions
              data-testid="zone-actions"
              deleteDisabled={!canBeDeleted}
              deleteTooltip={
                !canBeDeleted ? "Cannot delete the default zone." : null
              }
              onDelete={() => {
                openSidePanel({
                  component: DeleteZone,
                  title: "Delete AZ",
                  props: {
                    id: row.original.id,
                  },
                });
              }}
              onEdit={() => {
                openSidePanel({
                  component: EditZone,
                  title: "Edit AZ",
                  props: { id: row.original.id },
                });
              }}
            />
          );
        },
      },
    ],
    [isSuperUser.data, openSidePanel]
  );
};

export default useZonesTableColumns;
