import type { Dispatch, ReactElement, SetStateAction } from "react";
import { useEffect, useState } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import type { RowSelectionState } from "@tanstack/react-table";

import { useGroupEntitlements } from "@/app/api/query/groups";
import type { EntitlementResponse, UserGroupResponse } from "@/app/apiclient";
import usePagination from "@/app/base/hooks/usePagination/usePagination";
import useGroupEntitlementsTableColumns from "@/app/settings/views/UserManagement/views/Groups/components/GroupEntitlementsTable/useGroupEntitlementsTableColumns/useGroupEntitlementsTableColumns";

type GroupEntitlementsTableProps = {
  id: UserGroupResponse["id"];
  entitlementSelection: EntitlementResponse[];
  setEntitlementSelection: Dispatch<SetStateAction<EntitlementResponse[]>>;
};

const GroupEntitlementsTable = ({
  id,
  entitlementSelection,
  setEntitlementSelection,
}: GroupEntitlementsTableProps): ReactElement => {
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const { page, size, handlePageSizeChange, setPage } = usePagination();

  const columns = useGroupEntitlementsTableColumns({
    group_id: id,
    setEntitlementSelection,
  });

  const { data, isPending } = useGroupEntitlements({
    path: { group_id: id! },
  });

  const entitlements = data?.items.map((entitlement) => ({
    ...entitlement,
    id: `${entitlement.entitlement}-${entitlement.resource_id}`,
  }));

  const handleRowSelectionChange: Dispatch<
    SetStateAction<RowSelectionState>
  > = (updater) => {
    setRowSelection((prev) => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      const selected = (entitlements ?? []).filter((e) => next[e.id]);
      setEntitlementSelection(selected.map(({ id: _id, ...rest }) => rest));
      return next;
    });
  };

  useEffect(() => {
    if (
      entitlementSelection.length === 0 &&
      Object.keys(rowSelection).some((key) => rowSelection[key])
    ) {
      setRowSelection({});
    }
  }, [entitlementSelection, rowSelection]);

  return (
    <GenericTable
      aria-label="Group entitlements table"
      className="groups-entitlements-table"
      columns={columns}
      data={entitlements ?? []}
      isLoading={isPending}
      noData="No group entitlements found."
      pagination={{
        currentPage: page,
        dataContext: "entitlements",
        handlePageSizeChange: handlePageSizeChange,
        isPending: isPending,
        itemsPerPage: size,
        setCurrentPage: setPage,
        totalItems: data?.total ?? 0,
      }}
      selection={{ rowSelection, setRowSelection: handleRowSelectionChange }}
    />
  );
};
export default GroupEntitlementsTable;
