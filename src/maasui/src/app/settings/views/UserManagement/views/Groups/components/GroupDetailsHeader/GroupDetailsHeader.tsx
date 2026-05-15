import type { Dispatch, ReactElement, SetStateAction } from "react";

import { Button, ContextualMenu } from "@canonical/react-components";
import { Link, useLocation } from "react-router";

import { useGroupStatistics } from "@/app/api/query/groups";
import type {
  EntitlementResponse,
  UserGroupMemberResponse,
  UserGroupResponse,
} from "@/app/apiclient";
import SectionHeader from "@/app/base/components/SectionHeader";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/settings/urls";
import AddEntitlement from "@/app/settings/views/UserManagement/views/Groups/components/AddEntitlement";
import AddMembers from "@/app/settings/views/UserManagement/views/Groups/components/AddMembers/AddMembers";
import DeleteGroup from "@/app/settings/views/UserManagement/views/Groups/components/DeleteGroup";
import EditGroup from "@/app/settings/views/UserManagement/views/Groups/components/EditGroup";
import RemoveGroupEntitlement from "@/app/settings/views/UserManagement/views/Groups/components/RemoveGroupEntitlement";
import RemoveGroupMember from "@/app/settings/views/UserManagement/views/Groups/components/RemoveGroupMember";

type GroupDetailsHeaderProps = {
  group: UserGroupResponse | undefined;
  loading: boolean;
  entitlementSelection: EntitlementResponse[];
  setEntitlementSelection: Dispatch<SetStateAction<EntitlementResponse[]>>;
  memberSelection: UserGroupMemberResponse[];
  setMemberSelection: Dispatch<SetStateAction<UserGroupMemberResponse[]>>;
};

const GroupDetailsHeader = ({
  group,
  loading,
  entitlementSelection,
  setEntitlementSelection,
  memberSelection,
  setMemberSelection,
}: GroupDetailsHeaderProps): ReactElement => {
  const { openSidePanel } = useSidePanel();
  const { pathname } = useLocation();

  const { data: statistics, isLoading: statisticsLoading } = useGroupStatistics(
    { query: { id: group?.id ? [group.id] : [] } },
    !!group?.id
  );

  const urlBase = `/settings/user-management/group/${group?.id}`;

  return (
    <SectionHeader
      buttons={[
        ...(pathname.startsWith(`${urlBase}/entitlements`)
          ? [
              <Button
                appearance="negative"
                disabled={entitlementSelection.length <= 0}
                onClick={() => {
                  openSidePanel({
                    component: RemoveGroupEntitlement,
                    title: "Remove entitlements",
                    props: {
                      group_id: group!.id,
                      entitlements: entitlementSelection,
                      setEntitlementSelection: setEntitlementSelection,
                    },
                  });
                }}
                type="button"
              >
                Remove entitlements
              </Button>,
              <Button
                onClick={() => {
                  openSidePanel({
                    component: AddEntitlement,
                    title: "Add entitlement",
                    props: {
                      group_id: group!.id,
                    },
                  });
                }}
                type="button"
              >
                Add entitlement
              </Button>,
            ]
          : [
              <Button
                appearance="negative"
                disabled={memberSelection.length <= 0}
                onClick={() => {
                  openSidePanel({
                    component: RemoveGroupMember,
                    props: {
                      groupId: group!.id,
                      members: memberSelection,
                      setMemberSelection: setMemberSelection,
                    },
                    title: "Remove members",
                  });
                }}
                type="button"
              >
                Remove members
              </Button>,
              <Button
                onClick={() => {
                  openSidePanel({
                    component: AddMembers,
                    title: "Add members",
                    props: {
                      groupId: group!.id,
                    },
                    size: "large",
                  });
                }}
                type="button"
              >
                Add members
              </Button>,
            ]),
        <ContextualMenu
          hasToggleIcon
          links={[
            {
              children: "Edit group...",
              onClick: () => {
                openSidePanel({
                  component: EditGroup,
                  title: "Edit group",
                  props: {
                    id: group!.id,
                  },
                });
              },
            },
            {
              children: "Delete group...",
              onClick: () => {
                openSidePanel({
                  component: DeleteGroup,
                  title: "Delete group",
                  props: {
                    id: group!.id,
                    user_count: statistics?.items[0]?.user_count ?? 0,
                  },
                });
              },
            },
          ]}
          position="right"
          toggleAppearance="positive"
          toggleLabel="Take action"
        />,
      ]}
      loading={loading || statisticsLoading}
      tabLinks={[
        {
          active: pathname.startsWith(`${urlBase}/entitlements`),
          component: Link,
          label: "Entitlements",
          to: `${urlBase}/entitlements`,
        },
        {
          active: pathname.startsWith(`${urlBase}/members`),
          component: Link,
          label: "Members",
          to: `${urlBase}/members`,
        },
      ]}
      title={
        <>
          {group ? group.name : "Group"}
          <Link
            className="u-nudge-right"
            style={{ fontSize: "1rem" }}
            to={urls.userManagement.groups}
          >
            &lsaquo; Back to all groups
          </Link>
        </>
      }
    />
  );
};

export default GroupDetailsHeader;
