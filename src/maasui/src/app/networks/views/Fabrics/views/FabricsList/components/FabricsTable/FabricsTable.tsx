import { GenericTable } from "@canonical/maas-react-components";
import { Notification as NotificationBanner } from "@canonical/react-components";

import useFabricsTableColumns from "./useFabricsTableColumns/useFabricsTableColumns";

import { useFabrics } from "@/app/api/query/fabrics";
import usePagination from "@/app/base/hooks/usePagination/usePagination";

const FabricsTable = () => {
  const { page, debouncedPage, size, handlePageSizeChange, setPage } =
    usePagination();
  const { data, isPending, error, isError } = useFabrics({
    query: { page: debouncedPage, size },
  });
  const columns = useFabricsTableColumns();

  if (isError) {
    return (
      <NotificationBanner title="Error while fetching fabrics">
        {error.message}
      </NotificationBanner>
    );
  }

  return (
    <GenericTable
      aria-label="Fabrics table"
      columns={columns}
      data={data?.items ?? []}
      isLoading={isPending}
      noData="No fabrics found."
      pagination={{
        currentPage: page,
        dataContext: "fabrics",
        handlePageSizeChange,
        isPending: isPending,
        itemsPerPage: size,
        setCurrentPage: setPage,
        totalItems: data?.total ?? 0,
      }}
    />
  );
};

export default FabricsTable;
