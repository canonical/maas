import { useMemo } from "react";

import { Icon } from "@canonical/react-components";
import type { ColumnDef } from "@tanstack/react-table";
import { useLocation, Link } from "react-router";

import { useSidePanel } from "@/app/base/side-panel-context";
import type { SetSearchFilter } from "@/app/base/types";
import type { FormattedCloneError } from "@/app/machines/components/MachineForms/MachineActionFormWrapper/CloneForm/CloneResults/CloneResults";
import { FilterMachines } from "@/app/store/machine/utils";

export type CloneResultColumnDef = ColumnDef<
  FormattedCloneError,
  Partial<FormattedCloneError>
>;

const useCloneResultsColumns = ({
  failedCount,
  setSearchFilter,
}: {
  failedCount: number;
  setSearchFilter?: SetSearchFilter;
}): CloneResultColumnDef[] => {
  const { closeSidePanel } = useSidePanel();
  const { pathname } = useLocation();

  return useMemo(
    (): CloneResultColumnDef[] => [
      {
        id: "error",
        accessorKey: "description",
        enableSorting: false,
        header: "Error",
        cell: ({
          row: {
            original: { description },
          },
        }) => (
          <>
            <Icon name="error" />
            <span className="u-nudge-right" data-testid="error-description">
              {description}
            </span>
          </>
        ),
      },
      {
        id: "affectedMachines",
        accessorKey: "destinations",
        enableSorting: false,
        header: "Affected machines",
        cell: ({ row: { original: error } }) => {
          const filters = error.destinations
            ? { system_id: error.destinations }
            : null;
          return (
            <>
              <span className="u-nudge-left--small">{failedCount}</span>
              {filters ? (
                <Link
                  data-testid="error-filter-link"
                  onClick={() => {
                    if (setSearchFilter) {
                      closeSidePanel();
                      setSearchFilter(FilterMachines.filtersToString(filters));
                    }
                  }}
                  to={`${pathname}${FilterMachines.filtersToQueryString(
                    filters
                  )}`}
                >
                  Show
                </Link>
              ) : null}
            </>
          );
        },
      },
    ],
    [closeSidePanel, failedCount, pathname, setSearchFilter]
  );
};

export default useCloneResultsColumns;
