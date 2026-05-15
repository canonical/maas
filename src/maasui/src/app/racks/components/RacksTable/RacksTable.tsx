import { GenericTable } from "@canonical/maas-react-components";

import useRacksTableColumns from "./useRacksTableColumns/useRacksTableColumns";

import { useRacks } from "@/app/api/query/racks";
import usePagination from "@/app/base/hooks/usePagination/usePagination";

const RacksTable = () => {
  const { page, debouncedPage, size, handlePageSizeChange, setPage } =
    usePagination();

  const racks = useRacks({
    query: { page: debouncedPage, size },
  });

  const columns = useRacksTableColumns();

  return (
    <GenericTable
      columns={columns}
      data={racks.data?.items ?? []}
      isLoading={racks.isPending}
      noData="No racks found."
      pagination={{
        currentPage: page,
        dataContext: "racks",
        handlePageSizeChange: handlePageSizeChange,
        isPending: false,
        itemsPerPage: size,
        setCurrentPage: setPage,
        totalItems: racks.data?.total || 0,
      }}
    />
  );
};

export default RacksTable;
