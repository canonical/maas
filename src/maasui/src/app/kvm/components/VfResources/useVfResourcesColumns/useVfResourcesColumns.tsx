import { useMemo } from "react";

import type { ColumnDef, Row } from "@tanstack/react-table";

import type { PodNetworkInterface } from "@/app/store/pod/types";

type VfResourceColumnDef = ColumnDef<
  PodNetworkInterface,
  Partial<PodNetworkInterface>
>;

const useVfResourcesColumns = (): VfResourceColumnDef[] => {
  return useMemo(
    () => [
      {
        id: "name",
        accessorKey: "name",
        enableSorting: false,
        header: () => <span className="u-text--light">Interface</span>,
      },
      {
        id: "allocated",
        accessorKey: "allocated",
        enableSorting: false,
        header: () => (
          <span className="u-text--light u-truncate">
            Allocated
            <span className="u-nudge-right--small">
              <i className="p-circle--link"></i>
            </span>
          </span>
        ),
        cell: ({
          row: {
            original: {
              virtual_functions: { allocated_tracked, allocated_other },
            },
          },
        }: {
          row: Row<PodNetworkInterface>;
        }) => {
          const allocated = allocated_tracked + allocated_other;
          return allocated ? (
            <span className="u-text--light u-truncate">
              {allocated}
              <span className="u-nudge-right--small">
                <i className="p-circle--link"></i>
              </span>
            </span>
          ) : (
            <span>&mdash;</span>
          );
        },
      },
      {
        id: "free",
        accessorKey: "free",
        enableSorting: false,
        header: () => (
          <span className="u-text--light u-truncate">
            Free
            <span className="u-nudge-right--small">
              <i className="p-circle--link-faded"></i>
            </span>
          </span>
        ),
        cell: ({
          row: {
            original: {
              virtual_functions: { free },
            },
          },
        }: {
          row: Row<PodNetworkInterface>;
        }) =>
          free ? (
            <span className="u-text--light u-truncate">
              {free}
              <span className="u-nudge-right--small">
                <i className="p-circle--link-faded"></i>
              </span>
            </span>
          ) : (
            <span>&mdash;</span>
          ),
      },
    ],
    []
  );
};

export default useVfResourcesColumns;
