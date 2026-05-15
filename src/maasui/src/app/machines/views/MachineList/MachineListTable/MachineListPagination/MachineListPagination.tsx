import { useState, useRef, useEffect } from "react";

import { Pagination } from "@canonical/maas-react-components";
import type {
  PaginationProps,
  PropsWithSpread,
} from "@canonical/react-components";

import { useFetchedCount } from "@/app/store/machine/utils";

export enum Label {
  Pagination = "Table pagination",
  PreviousPage = "Previous page",
  NextPage = "Next page",
}

export const DEFAULT_DEBOUNCE_INTERVAL = 500;

export type Props = PropsWithSpread<
  {
    currentPage: PaginationProps["currentPage"];
    itemsPerPage: PaginationProps["itemsPerPage"];
    machineCount: number | null;
    totalPages: number | null;
    machinesLoading?: boolean | null;
    paginate: NonNullable<PaginationProps["paginate"]>;
  },
  Partial<PaginationProps>
>;

const MachineListPagination = ({
  machineCount,
  machinesLoading,
  totalPages,
  ...props
}: Props): React.ReactElement | null => {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const [pageNumber, setPageNumber] = useState<number | undefined>(
    props.currentPage
  );
  const [error, setError] = useState("");

  // Clear the timeout when the component is unmounted.
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearTimeout(intervalRef.current);
      }
    };
  }, []);

  const count = useFetchedCount(machineCount, machinesLoading);
  const pages = useFetchedCount(totalPages, machinesLoading);

  return count > 0 ? (
    <div className="p-pagination--machines">
      <Pagination
        aria-label={Label.Pagination}
        currentPage={pageNumber}
        disabled={false}
        error={error}
        onInputBlur={() => {
          setPageNumber(props.currentPage);
          setError("");
        }}
        onInputChange={(e) => {
          if (e.target.value) {
            setPageNumber(e.target.valueAsNumber);
            if (intervalRef.current) {
              clearTimeout(intervalRef.current);
            }
            intervalRef.current = setTimeout(() => {
              if (
                e.target.valueAsNumber > pages ||
                e.target.valueAsNumber < 1
              ) {
                setError(
                  `"${e.target.valueAsNumber}" is not a valid page number.`
                );
              } else {
                setError("");
                props.paginate(e.target.valueAsNumber);
              }
            }, DEFAULT_DEBOUNCE_INTERVAL);
          } else {
            setPageNumber(undefined);
            setError("Enter a page number.");
          }
        }}
        onNextClick={() => {
          setPageNumber((page) => Number(page) + 1);
          props.paginate(Number(props.currentPage) + 1);
        }}
        onPreviousClick={() => {
          setPageNumber((page) => Number(page) - 1);
          props.paginate(Number(props.currentPage) - 1);
        }}
        totalPages={pages}
      />
    </div>
  ) : null;
};

export default MachineListPagination;
