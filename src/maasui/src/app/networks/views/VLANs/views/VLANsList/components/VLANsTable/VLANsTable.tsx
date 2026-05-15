import { useEffect } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { useDispatch, useSelector } from "react-redux";

import useVlansTableColumns from "./useVlansTableColumns/useVlansTableColumns";

import usePagination from "@/app/base/hooks/usePagination/usePagination";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";

const VLANsTable = () => {
  const dispatch = useDispatch();
  const vlans = useSelector(vlanSelectors.all);
  const loading = useSelector(vlanSelectors.loading);
  const loaded = useSelector(vlanSelectors.loaded);

  const columns = useVlansTableColumns();

  useEffect(() => {
    if (!loaded) dispatch(vlanActions.fetch());
  }, [dispatch, loaded]);

  const { page, size, handlePageSizeChange, setPage } = usePagination(50);

  return (
    <GenericTable
      aria-label="VLANs table"
      columns={columns}
      data={vlans.slice((page - 1) * size, page * size)}
      isLoading={loading}
      noData={"No VLANs found."}
      pagination={{
        currentPage: page,
        dataContext: "VLANs",
        handlePageSizeChange,
        isPending: loading,
        itemsPerPage: size,
        setCurrentPage: setPage,
        totalItems: vlans.length,
      }}
    />
  );
};

export default VLANsTable;
