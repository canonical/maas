import { useState } from "react";

import { GenericTable, MainToolbar } from "@canonical/maas-react-components";
import { Button, SearchBox } from "@canonical/react-components";

import AddGroup from "../AddGroup";

import useGroupsListColumns from "./useGroupsTableColumns/useGroupsTableColumns";

import { useGroups } from "@/app/api/query/groups";
import usePagination from "@/app/base/hooks/usePagination/usePagination";
import { useSidePanel } from "@/app/base/side-panel-context";

const GroupsTable = () => {
  const [searchText, setSearchText] = useState("");
  const { openSidePanel } = useSidePanel();
  const { page, debouncedPage, size, handlePageSizeChange, setPage } =
    usePagination();
  const columns = useGroupsListColumns();
  const groups = useGroups({
    query: { page: debouncedPage, size, group_name: searchText },
  });
  const groupsData = (groups.data?.items ?? []).map((item) => ({
    ...item,
    description: item.description as string | undefined,
    user_count: item.statistics?.user_count,
  }));
  return (
    <div className="groups-list">
      <MainToolbar>
        <MainToolbar.Title>Groups</MainToolbar.Title>
        <MainToolbar.Controls>
          <SearchBox
            onChange={setSearchText}
            placeholder="Search groups"
            value={searchText}
          />
          <Button
            onClick={() => {
              openSidePanel({
                component: AddGroup,
                title: "Add group",
              });
            }}
          >
            Add group
          </Button>
        </MainToolbar.Controls>
      </MainToolbar>
      <GenericTable
        columns={columns}
        data={groupsData}
        isLoading={groups.isPending}
        noData="No groups found."
        pagination={{
          currentPage: page,
          dataContext: "groups",
          handlePageSizeChange: handlePageSizeChange,
          isPending: groups.isPending,
          itemsPerPage: size,
          setCurrentPage: setPage,
          totalItems: groups.data?.total ?? 0,
        }}
      />
    </div>
  );
};
export default GroupsTable;
