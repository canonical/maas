# API Query and Mutation Hooks Standards

## TL;DR

- Auto-generated SDK lives in `src/app/apiclient`
- Manually write hooks in `src/app/api/query/` using the generated react-query.ts hooks
- Use `useWebsocketAwareQuery` with `queryOptionsWithHeaders` for queries to auto-invalidate on websocket updates and include response headers
- Use `useMutation` with `mutationOptionsWithHeaders` and `invalidateQueries` in `onSuccess` for mutations
- Create mock resolvers in `src/testing/resolvers/` using MSW (Mock Service Worker)
- Test hooks using `renderHookWithProviders` and mock resolvers
- Follow naming convention: `use<ResourcePlural>` for list queries, `useGet<Resource>` for single-item queries, `use<Action><Resource>` for single-resource mutations, `use<Action><ResourcePlural>` or `useBulk<Action><Resource>` for bulk mutations

## Naming Conventions

| Hook type | Pattern | Example |
|---|---|---|
| List query | `use<ResourcePlural>` | `usePools`, `useUsers` |
| Single item query | `useGet<Resource>` | `useGetPool`, `useGetUser` |
| Derived query (via `select`) | `use<Resource><Derivation>` | `usePoolCount` |
| Create mutation | `useCreate<Resource>` | `useCreatePool` |
| Update mutation | `useUpdate<Resource>` | `useUpdatePool` |
| Delete mutation | `useDelete<Resource>` | `useDeletePool` |
| Bulk mutation (plural resource) | `use<Action><ResourcePlural>` | `useCreateSshKeys`, `useDeleteCustomImages` |
| Bulk mutation (explicit prefix) | `useBulk<Action><Resource>` | `useBulkSetConfigurations` |

Queries that use `select` to derive data from a list query should be named `use<Resource><Derivation>` — not `useGet*`. `useGet*` is reserved for single-item queries that fetch by ID.

## Overview

Our API layer follows a three-tier architecture:

1. **Auto-generated SDK** (`src/app/apiclient`) - Generated from OpenAPI spec
2. **Custom hooks** (`src/app/api/query/`) - Manually written React Query hooks
3. **Mock resolvers** (`src/testing/resolvers/`) - MSW handlers for testing

## Writing Query Hooks

### Basic List Query

Use `useWebsocketAwareQuery` with `queryOptionsWithHeaders` to automatically invalidate when websocket updates occur and include response headers:

```typescript
export const useUsers = (options?: Options<ListUsersWithSummaryData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      ListUsersWithSummaryResponses,
      ListUsersWithSummaryErrors,
      ListUsersWithSummaryData
    >(options, listUsersWithSummary, listUsersWithSummaryQueryKey(options))
  );
};
```

### Single Item Query

```typescript
export const useGetUser = (options: Options<GetUserData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<GetUserResponses, GetUserErrors, GetUserData>(
      options,
      getUser,
      getUserQueryKey(options)
    )
  );
};
```

### Derived Queries

For queries that transform data, use the `select` option:

```typescript
export const useUserCount = (options?: Options<ListUsersWithSummaryData>) => {
  return useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      ListUsersWithSummaryResponses,
      ListUsersWithSummaryErrors,
      ListUsersWithSummaryData
    >(options, listUsersWithSummary, listUsersWithSummaryQueryKey(options)),
    select: (data) => data?.total ?? 0,
  });
};
```

## Writing Mutation Hooks

### Basic Mutation

Always invalidate related queries in `onSuccess`. Use `mutationOptionsWithHeaders` to include response headers:

```typescript
export const useCreateUser = (mutationOptions?: Options<CreateUserData>) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      CreateUserResponses,
      CreateUserErrors,
      CreateUserData
    >(mutationOptions, createUser),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listUsersWithSummaryQueryKey(),
      });
    },
  });
};
```

### Update Mutation

```typescript
export const useUpdateUser = (mutationOptions?: Options<UpdateUserData>) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      UpdateUserResponses,
      UpdateUserErrors,
      UpdateUserData
    >(mutationOptions, updateUser),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listUsersWithSummaryQueryKey(),
      });
    },
  });
};
```

### Delete Mutation

```typescript
export const useDeleteUser = (mutationOptions?: Options<DeleteUserData>) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      DeleteUserResponses,
      DeleteUserErrors,
      DeleteUserData
    >(mutationOptions, deleteUser),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listUsersWithSummaryQueryKey(),
      });
    },
  });
};
```

## WebSocket-Aware Queries

`useWebsocketAwareQuery` wraps `useQuery` with two additional behaviours:

1. **WebSocket NOTIFY invalidation** — when the WebSocket sends a NOTIFY message for a model that maps to this query's key, the query is automatically invalidated and refetched.
2. **Reconnect invalidation** — when the WebSocket reconnects (tracked via `connectedCount` from Redux status selectors), the query is invalidated so stale data is not shown.

Always use `useWebsocketAwareQuery` with `queryOptionsWithHeaders` for all queries. Never use bare `useQuery`.

```typescript
export const usePools = (
  options?: Options<ListResourcePoolsStatisticsData>
) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      ListResourcePoolsStatisticsResponses,
      ListResourcePoolsStatisticsErrors,
      ListResourcePoolsStatisticsData
    >(
      options,
      listResourcePoolsStatistics,
      listResourcePoolsStatisticsQueryKey(options)
    )
  );
};
```

### Adding Real-Time Updates for a New Resource

The model-to-query-key mapping lives in `wsToQueryKeyMapping` in `src/app/api/query/base.ts`. To wire up WebSocket invalidation for a new resource, add its mapping there:

```typescript
const wsToQueryKeyMapping: Partial<Record<WebSocketEndpointModel, unknown>> = {
  zone: listZonesWithStatisticsQueryKey(),
  sshkey: listUserSshkeysQueryKey(),
};
```

Add an entry using the `WebSocketEndpointModel` value for the resource and the corresponding generated query key function called with no arguments.

## Writing Mock Resolvers

Mock resolvers use [MSW (Mock Service Worker)](https://mswjs.io/) to intercept HTTP requests during testing. Create a resolver file in `src/testing/resolvers/` for each resource.

### Resolver Structure

Each resolver file should follow this structure:

1. **Mock data constants** - Default response data using factories
2. **Error constants** - Default error responses for each operation
3. **Resolver object** - Contains handlers for each endpoint operation
4. **Exports** - Export both the resolvers and mock data

### Key Principles

- **Overridable responses**: Both `handler()` and `error()` functions should accept optional parameters to override default responses
- **Resolved flag**: Track when a resolver has been called using a `resolved` boolean
- **Default errors**: Provide sensible default error objects that can be overridden
- **Use factories**: Generate mock data using factory functions for consistency

### Complete Example

```typescript
// 1. Define default mock data using factories
const mockUsers: ListUsersWithSummaryResponse = {
  items: [
    userFactory({ id: 1, email: "user1@example.com", username: "user1" }),
    userFactory({ id: 2, email: "user2@example.com", username: "user2" }),
  ],
  total: 2,
};

// 2. Define default error responses
const mockListUsersError: ListUsersError = {
  message: "Unauthorized",
  code: 401,
  kind: "Error", // Always "Error" for error responses
};

const mockGetUserError: GetUserError = {
  message: "Not found",
  code: 404,
  kind: "Error",
};

const mockCreateUserError: CreateUserError = {
  message: "A user with this username already exists.",
  code: 409,
  kind: "Error",
};

// 3. Create the resolver object
const usersResolvers = {
  listUsers: {
    resolved: false,
    // Handler accepts optional data parameter to override default response
    handler: (data: ListUsersWithSummaryResponse = mockUsers) =>
      http.get(`${BASE_URL}MAAS/a/v3/users_with_summary`, () => {
        usersResolvers.listUsers.resolved = true;
        return HttpResponse.json(data);
      }),
    // Error handler accepts optional error parameter to override default
    error: (error: ListUsersError = mockListUsersError) =>
      http.get(`${BASE_URL}MAAS/a/v3/users_with_summary`, () => {
        usersResolvers.listUsers.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  getUser: {
    resolved: false,
    // For single item queries, extract ID from params
    handler: () =>
      http.get(`${BASE_URL}MAAS/a/v3/users/:id`, ({ params }) => {
        const id = Number(params.id);
        const user = mockUsers.items.find((user) => user.id === id);
        usersResolvers.getUser.resolved = true;
        return user ? HttpResponse.json(user) : HttpResponse.error();
      }),
    error: (error: GetUserError = mockGetUserError) =>
      http.get(`${BASE_URL}MAAS/a/v3/users/:id`, () => {
        usersResolvers.getUser.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  createUser: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/users`, () => {
        usersResolvers.createUser.resolved = true;
        return HttpResponse.json({ id: 1 });
      }),
    error: (error: CreateUserError = mockCreateUserError) =>
      http.post(`${BASE_URL}MAAS/a/v3/users`, () => {
        usersResolvers.createUser.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  updateUser: {
    resolved: false,
    handler: () =>
      http.put(`${BASE_URL}MAAS/a/v3/users/:id`, () => {
        usersResolvers.updateUser.resolved = true;
        return HttpResponse.json({});
      }),
    error: (error: UpdateUserError) =>
      http.put(`${BASE_URL}MAAS/a/v3/users/:id`, () => {
        usersResolvers.updateUser.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  deleteUser: {
    resolved: false,
    handler: () =>
      http.delete(`${BASE_URL}MAAS/a/v3/users/:id`, () => {
        usersResolvers.deleteUser.resolved = true;
        return HttpResponse.json({}, { status: 204 });
      }),
    error: (error: DeleteUserError) =>
      http.delete(`${BASE_URL}MAAS/a/v3/users/:id`, () => {
        usersResolvers.deleteUser.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
};

// 4. Export both resolvers and mock data for reuse in tests
export { usersResolvers, mockUsers };
```

### Using Resolvers in Tests

**Override default response data:**

```typescript
// Return empty list
mockServer.use(usersResolvers.listUsers.handler({ items: [], total: 0 }));

// Return specific data
mockServer.use(
  usersResolvers.listUsers.handler({
    items: [userFactory({ id: 999, username: "special-user" })],
    total: 1,
  })
);
```

**Override default errors:**

```typescript
// Custom error message
mockServer.use(
  usersResolvers.createUser.error({
    message: "Custom error message",
    code: 500,
    kind: "Error",
  })
);

// Use default error
mockServer.use(usersResolvers.createUser.error());
```

**Check if resolver was called:**

```typescript
await userEvent.click(screen.getByRole("button", { name: /save/i }));

await waitFor(() => {
  expect(usersResolvers.createUser.resolved).toBeTruthy();
});
```

## Testing Hooks

### Test Structure

```typescript
const mockServer = setupMockServer(
  usersResolvers.listUsers.handler(),
  usersResolvers.createUser.handler()
);

describe("useUsers", () => {
  it("should return users data", async () => {
    const { result } = renderHookWithProviders(() => useUsers());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toEqual(mockUsers);
  });

  it("should handle empty list", async () => {
    mockServer.use(usersResolvers.listUsers.handler({ items: [], total: 0 }));
    const { result } = renderHookWithProviders(() => useUsers());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data?.items).toHaveLength(0);
  });

  it("should handle errors", async () => {
    mockServer.use(usersResolvers.listUsers.error());
    const { result } = renderHookWithProviders(() => useUsers());
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});
```

### Testing Mutations

```typescript
describe("useCreateUser", () => {
  it("should create a new user", async () => {
    const newUser = {
      email: "new@example.com",
      username: "newuser",
      password: "password",
    };
    const { result } = renderHookWithProviders(() => useCreateUser());
    result.current.mutate({ body: newUser });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it("should handle creation errors", async () => {
    mockServer.use(
      usersResolvers.createUser.error({
        message: "User already exists",
        code: 409,
        kind: "Error",
      })
    );
    const { result } = renderHookWithProviders(() => useCreateUser());
    result.current.mutate({ body: { username: "test" } });
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    expect(result.current.error?.message).toBe("User already exists");
  });
});
```

### Testing Single Item Queries

```typescript
describe("useGetUser", () => {
  it("should return the correct user", async () => {
    const expectedUser = mockUsers.items[0];
    const { result } = renderHookWithProviders(() =>
      useGetUser({ path: { user_id: expectedUser.id } })
    );
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toEqual(expectedUser);
  });

  it("should return error if user does not exist", async () => {
    const { result } = renderHookWithProviders(() =>
      useGetUser({ path: { user_id: 999 } })
    );
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});
```

## Best Practices

1. **Naming Conventions**:

   - List queries: `use<ResourcePlural>` (e.g., `useUsers`, `usePools`)
   - Single item: `useGet<Resource>` (e.g., `useGetUser`, `useGetPool`)
   - Mutations: `use<Mutation><Resource>` (e.g., `useCreate<Resource>`, `useUpdate<Resource>`, `useDelete<Resource>`)
   - Derivations: `use<Resource><Derivation>` (e.g., `use<Resource>Count`)

2. **Query Invalidation**:

   - Always invalidate related queries after mutations
   - Use `invalidateQueries` with the appropriate query key from the generated SDK

3. **WebSocket Awareness**:

   - Use `useWebsocketAwareQuery` with `queryOptionsWithHeaders` for all queries to automatically invalidate on real-time updates
   - Map websocket models to query keys in `base.ts` if needed

4. **Type Safety**:

   - Always use the generated types from `@/app/apiclient`
   - Use `queryOptionsWithHeaders` and `mutationOptionsWithHeaders` with proper type parameters for automatic type inference
   - Type parameters follow the pattern: `<Responses, Errors, Data>`

5. **Error Handling**:

   - All error types have `message`, `code`, and `kind` fields
   - Use the `errors` prop on forms to display mutation errors

6. **Testing**:

   - Use `setupMockServer` to configure MSW handlers
   - Use `renderHookWithProviders` to test hooks with React Query context
   - Test success, error, and edge cases for all hooks
   - Use `waitFor` to wait for async operations

7. **Mock Data**:
   - Export mock data from resolver files for reuse in tests
   - Use factories to generate test data
   - Provide both success and error handlers for all endpoints

## Common Pitfalls

- **Don't** forget to invalidate queries after mutations - stale data is confusing for users
- **Don't** use `useQuery` directly - always use `useWebsocketAwareQuery` with `queryOptionsWithHeaders` for queries
- **Don't** use `useMutation` directly without `mutationOptionsWithHeaders` - you'll miss response headers
- **Don't** forget to export mock data from resolver files
- **Don't** forget to set `resolved` flag in resolvers - it's useful for testing
- **Don't** forget to handle empty states in tests
- **Don't** forget to provide all three type parameters (`Responses`, `Errors`, `Data`) to the utility functions

### Query Key Scoping in invalidateQueries

Always call the query key function with no arguments in `invalidateQueries` to invalidate the full list. Passing `options` only invalidates the specific page or filter combination, leaving other cached pages stale.

**Do** — invalidates every cached result for that resource:

```typescript
onSuccess: () => {
  return queryClient.invalidateQueries({
    queryKey: listResourcePoolsStatisticsQueryKey(),
  });
},
```

**Don't** — scopes invalidation to the exact query key matching `options`, leaving other cached pages stale:

```typescript
onSuccess: () => {
  return queryClient.invalidateQueries({
    queryKey: listResourcePoolsStatisticsQueryKey(options),
  });
},
```
