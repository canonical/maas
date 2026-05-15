import { GenericTable } from "@canonical/maas-react-components";
import { Notification as NotificationBanner } from "@canonical/react-components";

import useSpacesTableColumns from "./useSpacesTableColumns/useSpacesTableColumns";

import { useSpaces } from "@/app/api/query/spaces";
import usePagination from "@/app/base/hooks/usePagination/usePagination";

const SpacesTable = () => {
  const { page, debouncedPage, size, handlePageSizeChange, setPage } =
    usePagination();
  const { data, isPending, error, isError } = useSpaces({
    query: { page: debouncedPage, size },
  });
  const columns = useSpacesTableColumns();

  if (isError) {
    return (
      <NotificationBanner title="Error while fetching spaces">
        {error.message}
      </NotificationBanner>
    );
  }

  return (
    <GenericTable
      aria-label="Spaces table"
      columns={columns}
      data={data?.items ?? []}
      isLoading={isPending}
      noData="No spaces found."
      pagination={{
        currentPage: page,
        dataContext: "spaces",
        handlePageSizeChange,
        isPending: isPending,
        itemsPerPage: size,
        setCurrentPage: setPage,
        totalItems: data?.total ?? 0,
      }}
    />
  );
};

export default SpacesTable;
