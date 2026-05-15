import {
  useAddGroupEntitlement,
  useCreateGroup,
  useDeleteGroup,
  useGetGroup,
  useGroupEntitlements,
  useGroupMembers,
  useGroups,
  useAddGroupMembers,
  useUpdateGroup,
  useRemoveGroupMembers,
  useRemoveGroupEntitlements,
} from "@/app/api/query/groups";
import type { EntitlementRequest, UserGroupRequest } from "@/app/apiclient";
import { Entitlement } from "@/app/settings/views/UserManagement/views/Groups/constants";
import {
  groupsResolvers,
  mockGroupEntitlements,
  mockGroupMembers,
  mockGroups,
  mockGroupStatistics,
} from "@/testing/resolvers/groups";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  groupsResolvers.listGroups.handler(),
  groupsResolvers.listGroupsStatistics.handler(),
  groupsResolvers.getGroup.handler(),
  groupsResolvers.createGroup.handler(),
  groupsResolvers.updateGroup.handler(),
  groupsResolvers.deleteGroup.handler(),
  groupsResolvers.listGroupEntitlements.handler(),
  groupsResolvers.addGroupEntitlement.handler(),
  groupsResolvers.removeGroupEntitlement.handler(),
  groupsResolvers.listGroupMembers.handler(),
  groupsResolvers.addGroupMember.handler(),
  groupsResolvers.removeGroupMember.handler()
);

describe("useGroups", () => {
  it("should return groups data", async () => {
    const { result } = renderHookWithProviders(() => useGroups());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(mockGroups);
  });
});

describe("useGroupStatistics", () => {
  it("should return group statistics", async () => {
    const { result } = renderHookWithProviders(() =>
      useGroups({ query: { id: [1, 2, 3] } })
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    [0, 1, 2].forEach((i) => {
      expect(result.current.data?.items[i].statistics).toMatchObject(
        mockGroupStatistics.items[i]
      );
    });
  });
});

describe("useGetGroup", () => {
  it("should return the correct group", async () => {
    const expectedGroup = mockGroups.items[0];
    const { result } = renderHookWithProviders(() =>
      useGetGroup({ path: { group_id: expectedGroup.id } })
    );
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(expectedGroup);
  });

  it("should return error for non existing group", async () => {
    const { result } = renderHookWithProviders(() =>
      useGetGroup({ path: { group_id: 999 } })
    );
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});

describe("useCreateGroup", () => {
  it("should create a group successfully", async () => {
    const newGroup: UserGroupRequest = {
      name: "New Group",
      description: "This is a test group",
    };
    const { result } = renderHookWithProviders(() => useCreateGroup());
    result.current.mutate({ body: newGroup });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject({ id: 1 });
  });
});

describe("useUpdateGroup", () => {
  it("should update a group successfully", async () => {
    const updatedGroup: UserGroupRequest = {
      name: "Updated Group",
      description: "This is an updated test group",
    };
    const { result } = renderHookWithProviders(() => useUpdateGroup());
    result.current.mutate({ body: updatedGroup, path: { group_id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useDeleteGroup", () => {
  it("should delete a group successfully", async () => {
    const { result } = renderHookWithProviders(() => useDeleteGroup());
    result.current.mutate({ path: { group_id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useGroupEntitlements", () => {
  it("should return group entitlement data", async () => {
    const { result } = renderHookWithProviders(() =>
      useGroupEntitlements({ path: { group_id: 1 } })
    );
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(mockGroupEntitlements);
  });
});

describe("useAddGroupEntitlement", () => {
  it("should create a group entitlement successfully", async () => {
    const newEntitlement: EntitlementRequest = {
      entitlement: Entitlement.CAN_VIEW_MACHINES,
      resource_id: 0,
      resource_type: "maas",
    };
    const { result } = renderHookWithProviders(() => useAddGroupEntitlement());
    result.current.mutate({
      body: newEntitlement,
      path: {
        group_id: 1,
      },
    });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject({ id: 1 });
  });
});

describe("useRemoveGroupEntitlements", () => {
  it("should delete a group entitlement successfully", async () => {
    const { result } = renderHookWithProviders(() =>
      useRemoveGroupEntitlements()
    );
    result.current.mutate({
      path: { group_id: 1 },
      body: {
        items: [
          {
            resource_type: "maas",
            resource_id: 0,
            entitlement: Entitlement.CAN_VIEW_MACHINES,
          },
        ],
      },
    });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useGroupMembers", () => {
  it("should return group members data", async () => {
    const { result } = renderHookWithProviders(() =>
      useGroupMembers({ path: { group_id: 1 } })
    );
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(mockGroupMembers);
  });
});

describe("useAddGroupMembers", () => {
  it("should add a group member successfully", async () => {
    const { result } = renderHookWithProviders(() => useAddGroupMembers());
    result.current.mutate({
      body: { user_ids: [1] },
      path: { group_id: 1 },
    });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useRemoveGroupMembers", () => {
  it("should remove a group member successfully", async () => {
    const { result } = renderHookWithProviders(() => useRemoveGroupMembers());
    result.current.mutate({
      path: { group_id: 1 },
      query: {
        id: [1],
      },
    });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
