import { GenericTable } from "@canonical/maas-react-components";

import useSwitchesTableColumns from "./useSwitchesTableColumns/useSwitchesTableColumns";

import { useSwitches } from "@/app/api/query/switches";
import usePagination from "@/app/base/hooks/usePagination/usePagination";
import "./_index.scss";

const SwitchesTable = () => {
  const { page, debouncedPage, size, handlePageSizeChange, setPage } =
    usePagination();

  const switches = useSwitches({
    query: { page: debouncedPage, size },
  });

  const columns = useSwitchesTableColumns();

  return (
    <GenericTable
      aria-label="switches list"
      className="switches-table"
      columns={columns}
      data={switches.data?.items ?? []}
      isLoading={switches.isPending}
      noData="No switches available."
      pagination={{
        currentPage: page,
        dataContext: "switches",
        handlePageSizeChange,
        isPending: switches.isPending,
        itemsPerPage: size,
        setCurrentPage: setPage,
        totalItems: switches.data?.total ?? 0,
      }}
      sorting={[{ id: "name", desc: false }]}
    />
  );
};

export default SwitchesTable;
