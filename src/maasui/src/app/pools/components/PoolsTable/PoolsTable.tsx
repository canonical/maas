import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";

import usePoolsTableColumns from "./usePoolsTableColumns/usePoolsTableColumns";

import { usePools } from "@/app/api/query/pools";
import usePagination from "@/app/base/hooks/usePagination/usePagination";

const PoolsTable = (): ReactElement => {
  const { page, debouncedPage, size, handlePageSizeChange, setPage } =
    usePagination();

  const pools = usePools({
    query: { page: debouncedPage, size },
  });

  const columns = usePoolsTableColumns();

  return (
    <GenericTable
      columns={columns}
      data={pools.data?.items ?? []}
      isLoading={pools.isPending}
      noData="No pools found."
      pagination={{
        currentPage: page,
        dataContext: "pools",
        handlePageSizeChange: handlePageSizeChange,
        isPending: pools.isPending,
        itemsPerPage: size,
        setCurrentPage: setPage,
        totalItems: pools.data?.total ?? 0,
      }}
      sorting={[{ id: "machine_ready_count", desc: true }]}
      variant="full-height"
    />
  );
};

export default PoolsTable;
