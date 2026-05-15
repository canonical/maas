# Notifications

## TL;DR

- Notifications are created by the backend and persisted in the database.
- `useNotifications` polls `GET /notifications?only_active=true` every 30 seconds and on WebSocket NOTIFY events.
- `useNotifications` is called once, in `StatusBar` (rendered by `App.tsx`). Do not call it anywhere else.
- Backend categories (`success`, `error`, `warning`, `info`) are mapped to toast severity automatically.
- Dismissing a toast calls `DELETE /notifications/:id` and invalidates the notifications query.
- Toast IDs are derived from backend notification IDs via `convertBackendIdToToastNotificationId`.
- `useDismissNotification` is the mutation hook. `useDismissNotifications` is the dismiss handler wired to `<ToastNotificationProvider>`.
- Feature components do not trigger toasts directly.
- Do not call `useToastNotification()` from feature components.
- Do not add new polling intervals or parallel notification fetching.

---

## Architecture

The notification flow:

1. The backend creates a notification record in the database.
2. `useNotifications` (called once in `StatusBar`, which is rendered by `<App />`) uses `useListNotifications`, which calls `GET /notifications?only_active=true` on a 30-second `refetchInterval` and re-fetches on WebSocket NOTIFY events via `useWebsocketAwareQuery`.
3. New notifications (not already shown, tracked by `useRef`) are mapped to the appropriate toast method and displayed.
4. When the user dismisses a toast, the `onDismiss` handler passed to `<ToastNotificationProvider>` calls `useDismissNotifications`, which invokes `DELETE /notifications/:id` for each dismissed notification and invalidates the notifications query.

Toasts are backed by server-side records. They survive page refresh until explicitly dismissed.

### Where these hooks live

`useNotifications` is called in `StatusBar.tsx`, which is rendered by `App.tsx`. `useDismissNotification` and `useDismissNotifications` are wired directly in `App.tsx` at the `<ToastNotificationProvider>` level:

```tsx
const dismissMutation = useDismissNotification();
const dismiss = useDismissNotifications(dismissMutation.mutate);

return (
  <ToastNotificationProvider onDismiss={dismiss}>
    ...
  </ToastNotificationProvider>
);
```

---

## Hook Reference

### `useListNotifications`

Fetches active notifications. Wraps `useWebsocketAwareQuery` with a 30-second `refetchInterval`.

```ts
import { useListNotifications } from "@/app/api/query/notifications";

const { data } = useListNotifications({ query: { only_active: true } });
```

### `useNotifications`

Runs the full notification display loop. Calls `useListNotifications`, tracks shown IDs in a `useRef`, and calls the appropriate `useToastNotification` method for each new item.

```ts
import { useNotifications } from "@/app/api/query/notifications";

useNotifications();
```

Call this once in `<App />`. Do not call it in any other component.

### `useDismissNotification`

Mutation hook for `DELETE /notifications/:id`. Invalidates the notifications query on success.

```ts
import { useDismissNotification } from "@/app/api/query/notifications";

const dismissMutation = useDismissNotification();

dismissMutation.mutate({
  path: { notification_id: 42 },
});
```

### `useDismissNotifications`

Returns a handler that calls `useDismissNotification` for each `ToastNotificationType` in the array. This is the function passed to `<ToastNotificationProvider onDismiss={...}>`.

```ts
import {
  useDismissNotification,
  useDismissNotifications,
} from "@/app/api/query/notifications";

const dismissMutation = useDismissNotification();
const dismiss = useDismissNotifications(dismissMutation.mutate);
```

---

## Notification Categories

| Backend `category` | Toast method called | Visual severity |
|---|---|---|
| `success` | `notifications.success(...)` | Green |
| `error` | `notifications.failure(...)` | Red |
| `warning` | `notifications.caution(...)` | Yellow |
| `info` | `notifications.info(...)` | Blue |

The mapping is implemented in `useNotifications` in `src/app/api/query/notifications.ts` and requires no configuration in feature code.

---

## ID Conversion Utilities

Toast notification IDs are strings; backend notification IDs are numbers. Two helpers handle the conversion:

```ts
import {
  convertBackendIdToToastNotificationId,
  convertToastNotificationIdToBackendId,
} from "@/app/api/query/notifications";

convertBackendIdToToastNotificationId(42);   // "notification-42"
convertToastNotificationIdToBackendId("notification-42");  // 42
```

`convertToastNotificationIdToBackendId` throws if the string does not match the expected format.

---

## What Feature Components Should Do

In most cases, nothing. The backend creates notifications; `App.tsx` displays and dismisses them.

If a feature needs to programmatically dismiss a specific notification by its backend ID:

```ts
const dismissMutation = useDismissNotification();

dismissMutation.mutate({
  path: { notification_id: backendNotificationId },
});
```

---

## Dos and Don'ts

**Do** let the backend create notifications for persistent user-facing messages.

**Don't** call `useToastNotification()` directly in feature components — toast state is managed centrally.

**Do** use `useDismissNotification` if a feature needs to programmatically dismiss a specific notification.

**Don't** call `useNotifications()` outside of `App.tsx` — duplicate calls create duplicate toasts.

**Do** rely on `useDismissNotifications` being wired to `<ToastNotificationProvider onDismiss={...}>` — dismissal is already handled globally.

**Don't** add new `refetchInterval` values or additional calls to `useListNotifications` — the existing 30-second interval plus WebSocket invalidation is the intended polling strategy.
