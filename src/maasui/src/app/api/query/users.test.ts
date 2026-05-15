import {
  useCreateUser,
  useDeleteUser,
  useGetUser,
  useUpdateUser,
  useUserCount,
  useUsers,
  useUsersStatistics,
} from "@/app/api/query/users";
import type { UserCreateRequest, UserUpdateRequest } from "@/app/apiclient";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  mockUsers,
  mockUsersStatistics,
  usersResolvers,
} from "@/testing/resolvers/users";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

const mockServer = setupMockServer(
  usersResolvers.listUsers.handler(),
  usersResolvers.listUsersStatistics.handler(),
  usersResolvers.getUser.handler(),
  usersResolvers.createUser.handler(),
  usersResolvers.updateUser.handler(),
  usersResolvers.deleteUser.handler(),
  authResolvers.getCurrentUser.handler()
);

describe("useUsers", () => {
  it("should return users data", async () => {
    const { result } = renderHookWithProviders(() => useUsers());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(mockUsers);
  });
});

describe("useUsersStatistics", () => {
  it("should return users statistics data", async () => {
    const { result } = renderHookWithProviders(() => useUsersStatistics());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(mockUsersStatistics);
  });
});

describe("useUserCount", () => {
  it("should return correct count", async () => {
    const { result } = renderHookWithProviders(() => useUserCount());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toBe(3);
  });

  it("should return 0 when no users exist", async () => {
    mockServer.use(usersResolvers.listUsers.handler({ items: [], total: 0 }));
    const { result } = renderHookWithProviders(() => useUserCount());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toBe(0);
  });
});

describe("useGetUser", () => {
  it("should return the correct user", async () => {
    const expectedUser = mockUsers.items[0];
    const { result } = renderHookWithProviders(() =>
      useGetUser({ path: { user_id: expectedUser.id } })
    );
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(expectedUser);
  });

  it("should return error if user does not exist", async () => {
    const { result } = renderHookWithProviders(() =>
      useGetUser({ path: { user_id: 99 } })
    );
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});

describe("useCreateUser", () => {
  it("should create a new user", async () => {
    const newUser: UserCreateRequest = {
      email: "new.user@example.com",
      first_name: "Test",
      last_name: "User",
      is_superuser: false,
      password: "xxxx",
      username: "new-user",
    };
    const { result } = renderHookWithProviders(() => useCreateUser());
    result.current.mutate({ body: newUser });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useUpdateUser", () => {
  it("should update a user", async () => {
    const updatedUser: UserUpdateRequest = {
      email: "updated.user@example.com",
      first_name: "Test",
      last_name: "User",
      is_superuser: false,
      username: "updated-user",
    };
    const { result } = renderHookWithProviders(() => useUpdateUser());
    result.current.mutate({ body: updatedUser, path: { user_id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useDeleteUser", () => {
  it("should delete a user", async () => {
    const { result } = renderHookWithProviders(() => useDeleteUser());
    result.current.mutate({ path: { user_id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
