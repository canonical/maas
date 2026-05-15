# Routing

## TL;DR

- `src/router.tsx` is the single source of truth for all routes — one `createBrowserRouter` call.
- Every domain owns a `urls.ts` file; all domain url objects are aggregated in `src/app/base/urls.ts`.
- Use `argPath<T>(pattern)` for routes with dynamic segments; never write path strings by hand.
- Call `argPath(null)` in route definitions; call `argPath({ id })` when building links.
- Use `getRelativeRoute(absolute, base)` for paths inside nested route children.
- Wrap every route element in `<ErrorBoundary>`.
- All user-facing routes nest inside `<RequireLogin />` — do not add auth checks inside views.
- Lazy-load top-level view components with `React.lazy`; do not lazy-load sub-components.
- Public routes (`/login`, `/login/oidc/callback`) sit outside `<RequireLogin />`.
- Import from `urls` everywhere — never construct a path string directly.

---

## Route Tree Overview

`src/router.tsx` contains one `createBrowserRouter` call. Every route in the application is registered there.

Top-level structure:

```
/                         App (renders <Outlet />)
├── /login                Login
├── /login/oidc/callback  LoginCallback
└── (no path)             RequireLogin (renders <Outlet /> when authenticated)
    ├── /                 → redirect to /machines
    ├── /machines         Machines
    ├── /pools/*          PoolsList
    ├── /settings/*       Settings (nested children)
    └── ...               all other authenticated routes
```

`<App />` is the root element. It renders an `<Outlet />` into which the matched child route renders. `<RequireLogin />` is a pathless layout route — it checks authentication and renders `<Outlet />` when the user is logged in, or redirects to `/login` when not.

---

## URL Files

Every domain has a `urls.ts` at its root. Real example from `src/app/pools/urls.ts`:

```ts
import type { ResourcePoolResponse } from "@/app/apiclient";
import { argPath } from "@/app/utils";

const urls = {
  add: "/pools/add",
  edit: argPath<{ id: ResourcePoolResponse["id"] }>("/pools/:id/edit"),
  delete: argPath<{ id: ResourcePoolResponse["id"] }>("/pools/:id/delete"),
  index: "/pools",
};

export default urls;
```

`argPath<T>(pattern)` returns a function `(args: T | null) => string`:

- Pass `null` in route definitions to get the raw React Router pattern (e.g. `/pools/:id/edit`).
- Pass a real object when constructing a link (e.g. `urls.pools.edit({ id: pool.id })`).

All domain url objects are re-exported from `src/app/base/urls.ts`:

```ts
import { default as pools } from "@/app/pools/urls";

const urls = {
  index: "/",
  login: "/login",
  loginCallback: "/login/oidc/callback",
  pools,
  // ...other domains
} as const;

export default urls;
```

Import `urls` from `@/app/base/urls` everywhere — never reference a path as a bare string.

### Do

```ts
import urls from "@/app/base/urls";

<Link to={urls.pools.edit({ id: pool.id })}>Edit</Link>
```

### Don't

```ts
<Link to={`/pools/${pool.id}/edit`}>Edit</Link>
```

---

## Relative Routes

`getRelativeRoute(absolute, base)` strips the base prefix and the leading slash from a path. Use it for every child route inside a nested route group.

```ts
import { getRelativeRoute } from "@/app/utils";
import urls from "@/app/base/urls";

{
  path: urls.preferences.index,
  children: [
    {
      path: getRelativeRoute(urls.preferences.details, urls.preferences.index),
      element: (
        <ErrorBoundary>
          <Details />
        </ErrorBoundary>
      ),
    },
    {
      path: getRelativeRoute(urls.preferences.sshKeys, urls.preferences.index),
      element: (
        <ErrorBoundary>
          <SSHKeysList />
        </ErrorBoundary>
      ),
    },
  ],
}
```

For nested routes whose components themselves have dynamic segments, pass `null` in the parent `path` and apply `getRelativeRoute` on both sides:

```ts
{
  path: urls.machines.machine.index(null),
  children: [
    {
      path: getRelativeRoute(
        machineUrls.machine.summary(null),
        machineUrls.machine.index(null)
      ),
      element: <MachineSummary />,
    },
  ],
}
```

### Do

```ts
path: getRelativeRoute(urls.settings.configuration.general, urls.settings.index),
```

### Don't

```ts
path: "configuration/general",
```

---

## Lazy Loading

Lazy-load the top-level view component for every large domain view. Declarations go at the top of `src/router.tsx`, before the `createBrowserRouter` call.

```ts
const PoolsList = lazy(() => import("@/app/pools/views/PoolsList"));
```

Non-lazy imports are reserved for small views that are always needed on load (e.g. `Login`, `LoginCallback`, `RequireLogin`, `NotFound`).

### Do

```ts
const ZonesList = lazy(() => import("@/app/zones/views"));
```

### Don't

```ts
const PoolsTable = lazy(() => import("@/app/pools/views/PoolsList/PoolsTable"));
```

Only lazy-load top-level view components — not sub-components or components used inside views.

---

## Error Boundaries

Every route element must be wrapped in `<ErrorBoundary>`. This prevents a runtime error inside one view from crashing the entire application.

```tsx
{
  path: `${urls.pools.index}/*`,
  element: (
    <ErrorBoundary>
      <PoolsList />
    </ErrorBoundary>
  ),
}
```

When a route has nested children, each child element also receives its own `<ErrorBoundary>`:

```tsx
{
  path: getRelativeRoute(urls.settings.configuration.general, urls.settings.index),
  element: (
    <ErrorBoundary>
      <General />
    </ErrorBoundary>
  ),
}
```

### Do

Wrap every route element individually in `<ErrorBoundary>`.

### Don't

Rely on a single boundary at the layout level to catch errors from all children — each routable view needs its own boundary.

---

## Adding a New Route — Step by Step

1. **Create `src/app/<domain>/urls.ts`** (or add to an existing one). Use `argPath` for any segment that takes a dynamic value:

   ```ts
   import type { MyResourceResponse } from "@/app/apiclient";
   import { argPath } from "@/app/utils";

   const urls = {
     index: "/my-domain",
     add: "/my-domain/add",
     detail: argPath<{ id: MyResourceResponse["id"] }>("/my-domain/:id"),
   };

   export default urls;
   ```

2. **Export the domain urls from `src/app/base/urls.ts`**:

   ```ts
   import { default as myDomain } from "@/app/my-domain/urls";

   const urls = {
     // ...existing entries
     myDomain,
   } as const;
   ```

3. **Create the view component** under `src/app/<domain>/views/<ViewName>/<ViewName>.tsx`.

4. **Declare a lazy import** at the top of `src/router.tsx`:

   ```ts
   const MyDomainList = lazy(() => import("@/app/my-domain/views/MyDomainList"));
   ```

5. **Register the route** inside the `<RequireLogin />` children array, wrapped in `<ErrorBoundary>`:

   ```tsx
   {
     path: `${urls.myDomain.index}/*`,
     element: (
       <ErrorBoundary>
         <MyDomainList />
       </ErrorBoundary>
     ),
   }
   ```

6. **For nested routes**, add a `children` array and use `getRelativeRoute` for each child path:

   ```tsx
   {
     path: urls.myDomain.index,
     children: [
       {
         path: getRelativeRoute(urls.myDomain.add, urls.myDomain.index),
         element: (
           <ErrorBoundary>
             <AddMyResource />
           </ErrorBoundary>
         ),
       },
     ],
   }
   ```

---

## Dos and Don'ts

**Do** use `argPath` for every route with a dynamic segment.

**Don't** write `:id` patterns as bare strings in the router — define them via `argPath` in `urls.ts`.

**Do** use `getRelativeRoute(absolute, base)` for all paths inside a `children` array.

**Don't** hard-code relative strings like `"configuration/general"` directly in the router.

**Do** wrap every route `element` in `<ErrorBoundary>`.

**Don't** omit `<ErrorBoundary>` because a parent route already has one.

**Do** declare lazy views with `React.lazy` at the top of `src/router.tsx`.

**Don't** lazy-load sub-components or shared components — only top-level view entry points.

**Do** place all new authenticated routes inside the `<RequireLogin />` children array.

**Don't** add authentication or session-checking logic inside individual view components.
