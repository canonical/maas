import { useMemo } from "react";

import type { ColumnDef, Row } from "@tanstack/react-table";

import type { RamResource } from "@/app/kvm/components/RamResources/RamResources";
import { memoryWithUnit } from "@/app/kvm/utils";

type RamResourceColumnDef = ColumnDef<RamResource, Partial<RamResource>>;

const useRamResourcesColumns = ({
  pageSize,
  showOthers,
}: {
  pageSize: number;
  showOthers: boolean;
}): RamResourceColumnDef[] => {
  return useMemo(
    () => [
      {
        id: "type",
        accessorKey: "type",
        enableSorting: false,
        header: "",
        cell: ({
          row: {
            original: { type },
          },
        }: {
          row: Row<RamResource>;
        }) =>
          type === "Hugepage" ? (
            <>
              Hugepage
              {pageSize > 0 && (
                <>
                  <br />
                  <strong
                    className="p-text--x-small u-text--light"
                    data-testid="page-size"
                  >
                    {`(Size: ${memoryWithUnit(pageSize)})`}
                  </strong>
                </>
              )}
            </>
          ) : (
            "General"
          ),
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
            original: { allocated },
          },
        }: {
          row: Row<RamResource>;
        }) => memoryWithUnit(allocated),
      },
      ...(showOthers
        ? [
            {
              id: "others",
              accessorKey: "others",
              enableSorting: false,
              header: () => (
                <span className="u-text--light u-truncate">
                  Others
                  <span className="u-nudge-right--small">
                    <i className="p-circle--positive"></i>
                  </span>
                </span>
              ),
              cell: ({
                row: {
                  original: { others },
                },
              }: {
                row: Row<RamResource>;
              }) => memoryWithUnit(others),
            },
          ]
        : []),
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
            original: { free },
          },
        }: {
          row: Row<RamResource>;
        }) => memoryWithUnit(free),
      },
    ],
    [pageSize, showOthers]
  );
};

export default useRamResourcesColumns;
