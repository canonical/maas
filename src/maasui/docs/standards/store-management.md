# Store Management

## TL;DR

- Redux is legacy and being actively phased out — do not add new slices, actions, or sagas.
- Redux still covers WebSocket connection/messaging and a small number of legacy REST flows (login, licence keys).
- Use TanStack Query for all new REST endpoints.
- Read existing state with `useSelector` and a named selector from the slice's `selectors.ts`.
- Never write inline selector functions — always use the pre-built selectors.
- Trigger legacy data fetches with `useFetchActions` — only for flows already in Redux.
- Do not mock the Redux store in tests — pass state via `renderWithProviders`.
- Do not use `configureStore()` from `redux-mock-store` in new tests.
- Verify dispatched actions by reading `store.getActions()` from the `renderWithProviders` return value.
- When migrating a slice, replace selectors and fetch hooks with TanStack Query hooks, then remove the slice.

---

## What Redux Is Still Used For

Redux handles:

- WebSocket connection lifecycle and messaging (via Redux-Saga).
- A small number of legacy REST flows: authentication/session checks and licence keys.

Redux does not handle, and should not be extended to handle, any new REST endpoints. All new REST work goes in `src/app/api/query/` using TanStack Query.

---

## Reading from the Store

Use `useSelector` with a named selector from the slice's `selectors.ts` file.

**Do:**

```tsx
import { useSelector } from "react-redux";
import status from "@/app/store/status/selectors";

const connected = useSelector(status.connected);
const authenticated = useSelector(status.authenticated);
```

**Don't:**

```tsx
const connected = useSelector((state) => state.status.connected);
```

Selector files live at `src/app/store/<slice>/selectors.ts`. The status selectors available are: `authenticated`, `authenticating`, `authenticationError`, `connected`, `connecting`, `connectedCount`, `error`, `externalAuthURL`, `externalLoginURL`, `noUsers`.

---

## Triggering Data Fetches (Legacy Pattern)

`useFetchActions` dispatches a set of actions on mount and re-dispatches them whenever the WebSocket reconnects. Use it only for actions belonging to the legacy Redux flows listed above.

**Do:**

```tsx
import { useFetchActions } from "@/app/base/hooks";
import { statusActions } from "@/app/store/status";

useFetchActions([statusActions.checkAuthenticated]);
```

**Don't:**

```tsx
useEffect(() => {
  dispatch(statusActions.checkAuthenticated());
}, [dispatch]);
```

The inline `useEffect` approach does not re-fetch on WebSocket reconnect. `useFetchActions` handles reconnect automatically by watching `connectedCount` from the status selectors.

---

## Testing with Redux State

Pass state via `renderWithProviders`. Do not create a mock store manually.

**Do:**

```tsx
renderWithProviders(<MyComponent />, {
  state: factory.rootState({
    status: factory.statusState({ connected: true, authenticated: true }),
  }),
});

const { store } = renderWithProviders(<MyComponent />);
expect(store.getActions()).toContainEqual(someAction());
```

**Don't:**

```tsx
import configureStore from "redux-mock-store";

const store = configureStore([])({ status: { connected: true } });
render(
  <Provider store={store}>
    <MyComponent />
  </Provider>
);
```

`renderWithProviders` returns the store, which exposes `getActions()` for asserting dispatched actions.

---

## Migration Path

When migrating a feature away from Redux:

1. Create TanStack Query hooks in `src/app/api/query/<domain>.ts`.
2. Create MSW resolvers in `src/testing/resolvers/<domain>.ts`.
3. Replace `useSelector` calls with the new query hooks.
4. Replace `useFetchActions` calls with query hooks.
5. Remove the Redux slice once all consumers are migrated.

---

## Dos and Don'ts

- **Do** read from existing slices when data has not been migrated to TanStack Query yet.
- **Do** use named selectors from `src/app/store/<slice>/selectors.ts`.
- **Do** use `useFetchActions` for legacy actions that need reconnect-aware dispatch.
- **Do** pass state to tests via `renderWithProviders`.
- **Don't** add new Redux slices, actions, or sagas.
- **Don't** add new Redux-based REST endpoints.
- **Don't** write inline selector functions — always use the pre-built selectors.
- **Don't** use `configureStore()` from `redux-mock-store` in new tests.
