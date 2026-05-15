# Permissions

## TL;DR

- Two permission layers: user-level (`is_superuser`) and resource-level (`permissions[]`).
- Use `useGetIsSuperUser()` from `@/app/api/query/auth` to check admin status.
- Use `resource.permissions.includes("edit")` for per-resource operation checks.
- Use `useCanEdit` from `@/app/base/hooks` for all machine/device/controller nodes — do not replicate its logic.
- `useCanEdit` combines `permissions`, the `locked` flag, and rack controller connection state.
- Pass `true` as the second argument to `useCanEdit` to skip the rack controller check.
- Never check `is_superuser` for resource-level operations — use the `permissions` array.
- Never hide permission-protected actions with CSS — use conditional rendering.
- Test admin checks with `authResolvers.getCurrentUser.handler(factory.user({ is_superuser: true }))`.
- Test resource permissions with `factory.resourcePool({ permissions: ["edit", "delete"] })`.

---

## Layer 1 — User-Level (Admin Check)

`is_superuser` on the authenticated user controls admin-only UI. Use `useGetIsSuperUser` from `@/app/api/query/auth`:

```tsx
import { useGetIsSuperUser } from "@/app/api/query/auth";

const isSuperUser = useGetIsSuperUser();

{isSuperUser.data && <AdminOnlyButton />}
```

When you need the full user object alongside other fields, use `useGetCurrentUser` instead:

```tsx
import { useGetCurrentUser } from "@/app/api/query/auth";

const authUser = useGetCurrentUser();
const isAdmin = authUser.data?.is_superuser ?? false;
```

Use this layer for: showing or hiding admin-only actions, rendering admin-only sections, and conditional navigation.

---

## Layer 2 — Resource-Level (Permissions Array)

Resources returned by the API carry a `permissions` array. Check it directly on the resource object:

```tsx
const canEdit = pool.permissions.includes("edit");
const canDelete = pool.permissions.includes("delete");
```

Real usage from `src/app/pools/components/PoolsTable/usePoolsTableColumns/usePoolsTableColumns.tsx`:

```tsx
<TableActions
  deleteDisabled={
    !row.original.permissions.includes("delete") ||
    row.original.is_default ||
    row.original.machine_total_count > 0
  }
  editDisabled={!row.original.permissions.includes("edit")}
  onDelete={...}
  onEdit={...}
/>
```

Common values: `"edit"`, `"delete"`. Check `@/app/apiclient` for the full set of values available on any given resource type.

---

## useCanEdit (Node Resources)

For machine, device, and controller nodes, use `useCanEdit` — it combines the `permissions` array, the `locked` flag, and rack controller connection state into a single boolean:

```tsx
import { useCanEdit } from "@/app/base/hooks";

const canEdit = useCanEdit(node);
const canEditIgnoreRack = useCanEdit(node, true);
```

- First argument: a `Node` object, or `null`/`undefined` (returns `false` when absent).
- Second argument: `ignoreRackControllerConnection` — pass `true` when the operation does not depend on the rack controller being reachable (e.g. editing power configuration).

The hook is defined in `src/app/base/hooks/node.ts` and exported from `src/app/base/hooks/index.ts`. Do not replicate this logic inline.

### Do

```tsx
const canEdit = useCanEdit(machine, true);

<Button disabled={!canEdit} onClick={handleEdit}>
  Edit
</Button>
```

### Don't

```tsx
const canEdit =
  machine.permissions.includes("edit") && !machine.locked;
```

---

## Testing Permissions

### Admin check (Layer 1)

Use `authResolvers.getCurrentUser.handler` with a `factory.user` override. The default `factory.user()` produces `is_superuser: true`, so explicitly set both cases:

```tsx
import { factory } from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import { renderWithProviders, setupMockServer } from "@/testing/utils";

const mockServer = setupMockServer(
  authResolvers.getCurrentUser.handler()
);

it("hides admin action when user is not superuser", async () => {
  mockServer.use(
    authResolvers.getCurrentUser.handler(
      factory.user({ is_superuser: false })
    )
  );
  renderWithProviders(<MyComponent />);
  await waitFor(() => {
    expect(screen.queryByRole("button", { name: /admin action/i })).not.toBeInTheDocument();
  });
});

it("shows admin action when user is superuser", async () => {
  mockServer.use(
    authResolvers.getCurrentUser.handler(
      factory.user({ is_superuser: true })
    )
  );
  renderWithProviders(<MyComponent />);
  await waitFor(() => {
    expect(screen.getByRole("button", { name: /admin action/i })).toBeInTheDocument();
  });
});
```

### Resource permissions (Layer 2)

Pass a factory-built resource with the relevant `permissions` value:

```tsx
import { factory } from "@/testing/factories";

const editablePool = factory.resourcePool({ permissions: ["edit", "delete"] });
const readOnlyPool = factory.resourcePool({ permissions: [] });
```

For components that load resources via MSW resolvers, use the pool resolver:

```tsx
mockServer.use(
  poolsResolvers.listPools.handler({
    items: [factory.resourcePool({ permissions: ["edit", "delete"] })],
    total: 1,
  })
);
```

### useCanEdit (node resources)

Provide a node with the appropriate `permissions` and `locked` values, and control rack controller state via the general store state:

```tsx
const machine = factory.machineDetails({
  permissions: ["edit"],
  locked: false,
});

renderWithProviders(<MyComponent systemId={machine.system_id} />, {
  state: factory.rootState({
    machine: factory.machineState({
      items: [machine],
    }),
    general: factory.generalState({
      powerTypes: factory.powerTypesState({ data: [factory.powerType()] }),
    }),
  }),
});
```

Pass `factory.powerTypesState({ data: [] })` to simulate a disconnected rack controller.

---

## Dos and Don'ts

**Do** use `useGetIsSuperUser` for admin visibility checks.

**Don't** use `is_superuser` to gate resource-level operations such as edit or delete — use `resource.permissions.includes("edit")` instead.

---

**Do** use `useCanEdit` for machine, device, and controller nodes.

**Don't** re-implement the `locked` + `permissions` + rack-controller logic inline when `useCanEdit` already encapsulates it.

---

**Do** use conditional rendering to hide permission-protected actions.

**Don't** hide elements with CSS and leave the underlying action reachable.

---

**Do** test both the permitted and denied cases for every permission check.

**Don't** test only the happy path — a test that only checks an action is visible when allowed misses permission regressions.
