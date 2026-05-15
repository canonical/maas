import type { Dispatch, ReactElement, SetStateAction } from "react";
import { useEffect, useState } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import type { RowSelectionState } from "@tanstack/react-table";

import { useGroupMembers } from "@/app/api/query/groups";
import type {
  UserGroupMemberResponse,
  UserGroupResponse,
} from "@/app/apiclient";
import usePagination from "@/app/base/hooks/usePagination/usePagination";
import useGroupMembersTableColumns from "@/app/settings/views/UserManagement/views/Groups/components/GroupMembersTable/useGroupMembersTableColumns/useGroupMembersTableColumns";

type GroupMembersTableProps = {
  id: UserGroupResponse["id"];
  memberSelection: UserGroupMemberResponse[];
  setMemberSelection: Dispatch<SetStateAction<UserGroupMemberResponse[]>>;
};

const GroupMembersTable = ({
  id,
  memberSelection,
  setMemberSelection,
}: GroupMembersTableProps): ReactElement => {
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const { page, size, handlePageSizeChange, setPage } = usePagination();

  const columns = useGroupMembersTableColumns({
    groupId: id,
    setMemberSelection,
  });

  const { data, isPending } = useGroupMembers({
    path: { group_id: id! },
  });

  const members = data?.items.map((member) => ({
    ...member,
    id: member.user_id.toString(),
  }));

  const handleRowSelectionChange: Dispatch<
    SetStateAction<RowSelectionState>
  > = (updater) => {
    setRowSelection((prev) => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      const selected = (members ?? []).filter((e) => next[e.id]);
      setMemberSelection(
        selected.map(({ user_id, username, email }) => ({
          user_id,
          username,
          email,
        }))
      );
      return next;
    });
  };

  useEffect(() => {
    if (
      memberSelection.length === 0 &&
      Object.keys(rowSelection).some((key) => rowSelection[key])
    ) {
      setRowSelection({});
    }
  }, [memberSelection, rowSelection]);

  return (
    <GenericTable
      aria-label="Group members table"
      className="groups-members-table"
      columns={columns}
      data={members ?? []}
      isLoading={isPending}
      noData="No group members found."
      pagination={{
        currentPage: page,
        dataContext: "members",
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
export default GroupMembersTable;
