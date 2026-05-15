import { useEffect, useMemo, useState } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import type { ColumnDef, RowSelectionState } from "@tanstack/react-table";
import type { FormikContextType } from "formik";
import pluralize from "pluralize";
import * as Yup from "yup";

import { useAddGroupMembers, useGroupMembers } from "@/app/api/query/groups";
import type { UserWithStatistics } from "@/app/api/query/users";
import { useUsers } from "@/app/api/query/users";
import type { AddGroupMemberError, UserGroupResponse } from "@/app/apiclient";
import FormikForm from "@/app/base/components/FormikForm";
import SearchBox from "@/app/base/components/SearchBox";
import usePagination from "@/app/base/hooks/usePagination/usePagination";
import { useSidePanel } from "@/app/base/side-panel-context";

import "./_index.scss";

type AddMembersValues = {
  user_ids: number[];
};

type AddMembersProps = {
  groupId: UserGroupResponse["id"];
};

const AddMembersSchema = Yup.object().shape({
  user_ids: Yup.array()
    .of(Yup.number().required())
    .min(1, "At least one user is required."),
});

type AddMembersColumnDef = ColumnDef<
  UserWithStatistics,
  Partial<UserWithStatistics>
>;

const AddMembers = ({ groupId }: AddMembersProps) => {
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [selectedUserCount, setSelectedUserCount] = useState(0);
  const { closeSidePanel } = useSidePanel();

  const [searchText, setSearchText] = useState("");
  const { page, debouncedPage, size, handlePageSizeChange, setPage } =
    usePagination(20);

  const { data: users, isPending: usersPending } = useUsers({
    query: { page: debouncedPage, size, username_or_email: searchText },
  });

  const { data: members, isPending: membersPending } = useGroupMembers({
    path: { group_id: groupId },
  });

  const memberIds = useMemo(
    () => members?.items.map((member) => member.user_id),
    [members]
  );

  const isPending = usersPending || membersPending;

  const addMembers = useAddGroupMembers();

  const columns = useMemo(
    (): AddMembersColumnDef[] => [
      {
        id: "username",
        accessorKey: "username",
        enableSorting: true,
      },
      {
        id: "email",
        accessorKey: "email",
        enableSorting: true,
      },
    ],
    []
  );

  useEffect(() => {
    if (!memberIds) return;
    setRowSelection(
      Object.fromEntries(memberIds.map((id) => [String(id), true]))
    );
  }, [memberIds]);

  return (
    <FormikForm<AddMembersValues, AddGroupMemberError>
      aria-label="Add group members"
      errors={addMembers.error}
      initialValues={{
        user_ids: [],
      }}
      onCancel={closeSidePanel}
      onSubmit={(values) => {
        addMembers.mutate({
          body: {
            user_ids: values.user_ids,
          },
          path: { group_id: groupId },
        });
      }}
      onSuccess={closeSidePanel}
      resetOnSave
      saved={addMembers.isSuccess}
      saving={addMembers.isPending}
      submitLabel={`Add ${selectedUserCount} ${pluralize("member", selectedUserCount)}`}
      validationSchema={AddMembersSchema}
    >
      {({ setFieldValue }: FormikContextType<AddMembersValues>) => (
        <>
          <SearchBox
            onChange={setSearchText}
            placeholder="Search users"
            value={searchText}
          />
          <GenericTable
            className="add-members-table u-border"
            columns={columns}
            data={users?.items ?? []}
            isLoading={isPending}
            noData="No users found."
            pagination={{
              currentPage: page,
              dataContext: "users",
              handlePageSizeChange: handlePageSizeChange,
              isPending: isPending,
              itemsPerPage: size,
              setCurrentPage: setPage,
              totalItems: users?.total ?? 0,
            }}
            selection={{
              rowSelection,
              setRowSelection: (updater) => {
                setRowSelection((prev) => {
                  const next =
                    typeof updater === "function" ? updater(prev) : updater;
                  const newIds = Object.keys(next)
                    .filter((id) => !memberIds?.includes(Number(id)))
                    .map(Number);
                  setSelectedUserCount(newIds.length);
                  void setFieldValue("user_ids", newIds);
                  return next;
                });
              },
              filterSelectable: (row) => !memberIds?.includes(row.original.id),
            }}
            sorting={[{ id: "username", desc: false }]}
            variant="regular"
          />
        </>
      )}
    </FormikForm>
  );
};

export default AddMembers;
