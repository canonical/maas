import { http, HttpResponse } from "msw";

import { BASE_URL } from "../utils";

import type {
  CreateGroupError,
  GetGroupError,
  ListGroupEntitlementsError,
  ListGroupEntitlementsResponse,
  ListGroupsError,
  ListGroupsResponse,
  ListGroupsStatisticsError,
  ListGroupsStatisticsResponse,
  ListGroupMembersError,
  ListGroupMembersResponse,
  AddGroupMemberError,
  UpdateGroupError,
  DeleteGroupError,
  RemoveGroupEntitlementError,
  RemoveGroupMemberError,
} from "@/app/apiclient";
import { Entitlement } from "@/app/settings/views/UserManagement/views/Groups/constants";
import {
  group as groupFactory,
  groupStatistics as groupStatsFactory,
  groupEntitlements as groupEntitlementsFactory,
  groupMember as groupMemberFactory,
} from "@/testing/factories/groups";

const mockGroups: ListGroupsResponse = {
  items: [
    groupFactory({
      id: 1,
      name: "group1",
      description: "First group",
    }),
    groupFactory({
      id: 2,
      name: "group2",
      description: "Second group",
    }),
    groupFactory({
      id: 3,
      name: "group3",
      description: "Third group",
    }),
  ],
  total: 3,
};

const mockGroupStatistics: ListGroupsStatisticsResponse = {
  items: [
    groupStatsFactory({
      id: 1,
      user_count: 5,
    }),
    groupStatsFactory({
      id: 2,
      user_count: 10,
    }),
    groupStatsFactory({
      id: 3,
      user_count: 15,
    }),
  ],
  total: 3,
};

const mockGroupEntitlements: ListGroupEntitlementsResponse = {
  items: [
    groupEntitlementsFactory({
      entitlement: Entitlement.CAN_DEPLOY_MACHINES,
      resource_id: 0,
      resource_type: "pool",
    }),
    groupEntitlementsFactory({
      entitlement: Entitlement.CAN_VIEW_NOTIFICATIONS,
      resource_type: "maas",
    }),
  ],
  total: 2,
};

const mockGroupMembers: ListGroupMembersResponse = {
  items: [
    groupMemberFactory({
      user_id: 1,
      username: "alice",
      email: "alice@example.com",
    }),
    groupMemberFactory({
      user_id: 2,
      username: "bob",
      email: "bob@example.com",
    }),
  ],
  total: 2,
};

const mockListError = {
  message: "Unprocessable Entity",
  code: 422,
  kind: "Error",
};

const mockGetError = {
  message: "Not found",
  code: 404,
  kind: "Error",
};

const mockCreateGroupError = {
  message: "A group with this name already exists.",
  code: 409,
  kind: "Error",
};

const groupsResolvers = {
  listGroups: {
    resolved: false,
    handler: (data: ListGroupsResponse = mockGroups) =>
      http.get(`${BASE_URL}MAAS/a/v3/groups`, () => {
        groupsResolvers.listGroups.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListGroupsError = mockListError) =>
      http.get(`${BASE_URL}MAAS/a/v3/groups`, () => {
        groupsResolvers.listGroups.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  listGroupsStatistics: {
    resolved: false,
    handler: (data: ListGroupsStatisticsResponse = mockGroupStatistics) =>
      http.get(`${BASE_URL}MAAS/a/v3/groups:statistics`, () => {
        groupsResolvers.listGroupsStatistics.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListGroupsStatisticsError = mockListError) =>
      http.get(`${BASE_URL}MAAS/a/v3/groups:statistics`, () => {
        groupsResolvers.listGroupsStatistics.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  getGroup: {
    resolved: false,
    handler: () =>
      http.get(`${BASE_URL}MAAS/a/v3/groups/:id`, ({ params }) => {
        const id = Number(params.id);
        if (!id) return HttpResponse.error();

        const group = mockGroups.items.find((group) => group.id === id);
        groupsResolvers.getGroup.resolved = true;
        return group ? HttpResponse.json(group) : HttpResponse.error();
      }),
    error: (error: GetGroupError = mockGetError) =>
      http.get(`${BASE_URL}MAAS/a/v3/groups/:id`, () => {
        groupsResolvers.getGroup.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  createGroup: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/groups`, () => {
        groupsResolvers.createGroup.resolved = true;
        return HttpResponse.json({ id: 1 });
      }),
    error: (error: CreateGroupError = mockCreateGroupError) =>
      http.post(`${BASE_URL}MAAS/a/v3/groups`, () => {
        groupsResolvers.createGroup.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  updateGroup: {
    resolved: false,
    handler: () =>
      http.put(`${BASE_URL}MAAS/a/v3/groups/:id`, () => {
        groupsResolvers.updateGroup.resolved = true;
        return HttpResponse.json({});
      }),
    error: (error: UpdateGroupError = mockGetError) =>
      http.put(`${BASE_URL}MAAS/a/v3/groups/:id`, () => {
        groupsResolvers.updateGroup.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  deleteGroup: {
    resolved: false,
    handler: () =>
      http.delete(`${BASE_URL}MAAS/a/v3/groups/:id`, () => {
        groupsResolvers.deleteGroup.resolved = true;
        return HttpResponse.json({});
      }),
    error: (error: DeleteGroupError = mockGetError) =>
      http.delete(`${BASE_URL}MAAS/a/v3/groups/:id`, () => {
        groupsResolvers.deleteGroup.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  listGroupEntitlements: {
    resolved: false,
    handler: (data: ListGroupEntitlementsResponse = mockGroupEntitlements) =>
      http.get(`${BASE_URL}MAAS/a/v3/groups/:id/entitlements`, () => {
        groupsResolvers.listGroupEntitlements.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListGroupEntitlementsError = mockListError) =>
      http.get(`${BASE_URL}MAAS/a/v3/groups/:id/entitlements`, () => {
        groupsResolvers.listGroupEntitlements.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  addGroupEntitlement: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/groups/:id/entitlements`, () => {
        groupsResolvers.addGroupEntitlement.resolved = true;
        return HttpResponse.json({ id: 1 });
      }),
    error: (error: CreateGroupError = mockCreateGroupError) =>
      http.post(`${BASE_URL}MAAS/a/v3/groups/:id/entitlements`, () => {
        groupsResolvers.addGroupEntitlement.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  removeGroupEntitlement: {
    resolved: false,
    handler: () =>
      http.post(
        `${BASE_URL}MAAS/a/v3/groups/:id/entitlements:batch_delete`,
        () => {
          groupsResolvers.removeGroupEntitlement.resolved = true;
          return HttpResponse.json({});
        }
      ),
    error: (error: RemoveGroupEntitlementError = mockGetError) =>
      http.post(
        `${BASE_URL}MAAS/a/v3/groups/:id/entitlements:batch_delete`,
        () => {
          groupsResolvers.removeGroupEntitlement.resolved = true;
          return HttpResponse.json(error, { status: error.code });
        }
      ),
  },
  listGroupMembers: {
    resolved: false,
    handler: (data: ListGroupMembersResponse = mockGroupMembers) =>
      http.get(`${BASE_URL}MAAS/a/v3/groups/:id/members`, () => {
        groupsResolvers.listGroupMembers.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListGroupMembersError = mockListError) =>
      http.get(`${BASE_URL}MAAS/a/v3/groups/:id/members`, () => {
        groupsResolvers.listGroupMembers.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  addGroupMember: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/groups/:id/members:batch_create`, () => {
        groupsResolvers.addGroupMember.resolved = true;
        return HttpResponse.json({});
      }),
    error: (error: AddGroupMemberError = mockCreateGroupError) =>
      http.post(`${BASE_URL}MAAS/a/v3/groups/:id/members:batch_create`, () => {
        groupsResolvers.addGroupMember.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  removeGroupMember: {
    resolved: false,
    handler: () =>
      http.delete(`${BASE_URL}MAAS/a/v3/groups/:id/members`, () => {
        groupsResolvers.removeGroupMember.resolved = true;
        return HttpResponse.json({});
      }),
    error: (error: RemoveGroupMemberError = mockGetError) =>
      http.delete(`${BASE_URL}MAAS/a/v3/groups/:id/members`, () => {
        groupsResolvers.removeGroupMember.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
};

export {
  groupsResolvers,
  mockGroups,
  mockGroupStatistics,
  mockGroupEntitlements,
  mockGroupMembers,
};
