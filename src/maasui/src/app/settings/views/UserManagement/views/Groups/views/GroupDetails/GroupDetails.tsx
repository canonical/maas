import type { ReactElement } from "react";
import { useState } from "react";

import { Spinner } from "@canonical/react-components";
import { Navigate, Route, Routes } from "react-router";

import { useGetGroup } from "@/app/api/query/groups";
import type {
  EntitlementResponse,
  UserGroupMemberResponse,
} from "@/app/apiclient";
import ModelNotFound from "@/app/base/components/ModelNotFound";
import PageContent from "@/app/base/components/PageContent/PageContent";
import { useGetURLId, useWindowTitle } from "@/app/base/hooks";
import urls from "@/app/settings/urls";
import GroupDetailsHeader from "@/app/settings/views/UserManagement/views/Groups/components/GroupDetailsHeader";
import GroupEntitlementsTable from "@/app/settings/views/UserManagement/views/Groups/components/GroupEntitlementsTable/GroupEntitlementsTable";
import GroupMembersTable from "@/app/settings/views/UserManagement/views/Groups/components/GroupMembersTable/GroupMembersTable";
import { getRelativeRoute, isId } from "@/app/utils";

const GroupDetails = (): ReactElement => {
  const id = useGetURLId("id");
  const { data: group, isPending } = useGetGroup({
    path: { group_id: id! },
  });

  const isValidID = isId(id);

  const [entitlementSelection, setEntitlementSelection] = useState<
    EntitlementResponse[]
  >([]);
  const [memberSelection, setMemberSelection] = useState<
    UserGroupMemberResponse[]
  >([]);

  useWindowTitle(`${group?.name || "Group"} details`);

  if ((!group || !isValidID) && !isPending) {
    return (
      <ModelNotFound
        id={id}
        linkURL={urls.userManagement.groups}
        modelName="group"
      />
    );
  }

  const base = urls.userManagement.group.index(null);

  return (
    <PageContent
      header={
        <GroupDetailsHeader
          entitlementSelection={entitlementSelection}
          group={group}
          loading={isPending}
          memberSelection={memberSelection}
          setEntitlementSelection={setEntitlementSelection}
          setMemberSelection={setMemberSelection}
        />
      }
    >
      {isPending ? (
        <Spinner text="Loading..." />
      ) : (
        <Routes>
          <Route
            element={
              <Navigate
                replace
                to={urls.userManagement.group.entitlements({ id: id! })}
              />
            }
            index
          />
          <Route
            element={
              <GroupEntitlementsTable
                entitlementSelection={entitlementSelection}
                id={id!}
                setEntitlementSelection={setEntitlementSelection}
              />
            }
            path={getRelativeRoute(
              urls.userManagement.group.entitlements(null),
              base
            )}
          />
          <Route
            element={
              <GroupMembersTable
                id={id!}
                memberSelection={memberSelection}
                setMemberSelection={setMemberSelection}
              />
            }
            path={getRelativeRoute(
              urls.userManagement.group.members(null),
              base
            )}
          />
        </Routes>
      )}
    </PageContent>
  );
};

export default GroupDetails;
