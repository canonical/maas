# Side Panels

## TL;DR

- Use `useSidePanel()` to open and close panels — never manage panel visibility with local state or URL query params.
- Pass the component class to `openSidePanel`, not a JSX element.
- `title` renders as an `h3` in the panel header.
- `props` are typed via the `TProps` generic on `openSidePanel`.
- The panel auto-closes on any route change and when the user presses Escape.
- Call `closeSidePanel` on cancel and after a successful mutation.
- Three sizes: `regular` (default), `wide`, `large`. Change dynamically with `setSidePanelSize`.
- One panel per page — only one can be open at a time.
- Test with `mockSidePanel` from `@/testing/utils`. Always call it with `await` at the module level.
- `mockSidePanel` returns `{ mockOpen, mockClose }` for asserting open and close behaviour.

---

## Architecture

`SidePanelContextProvider` wraps the app. `<SidePanel />` lives inside `<PageContent />` and renders the `component` held in context.

```
SidePanelContextProvider
└── PageContent
    ├── <main content>
    └── SidePanel          ← renders context.component with context.props
```

`<PageContent />` always renders `<SidePanel />` — feature code never mounts the panel directly. Because a single context backs it, only one panel can be open at a time. Opening a second panel replaces the first.

---

## Opening a Side Panel

```tsx
import { useSidePanel } from "@/app/base/side-panel-context";
import { AddPool } from "@/app/pools/components";

const { openSidePanel } = useSidePanel();

openSidePanel({
  component: AddPool,
  title: "Add pool",
});
```

With props and an explicit size:

```tsx
openSidePanel({
  component: AddPool,
  title: "Add pool",
  props: { poolId: pool.id },
  size: "wide",
});
```

- `component` — the component class, not `<AddPool />`.
- `title` — rendered as an `h3` inside the panel header.
- `props` — typed through the `TProps` generic; defaults to `{}`.
- `size` — optional; defaults to `"regular"`.

Real-world example from `PoolsListHeader`:

```tsx
openSidePanel({ component: AddPool, title: "Add pool" });
```

---

## Closing a Side Panel

```tsx
const { closeSidePanel } = useSidePanel();

<Button onClick={closeSidePanel}>Cancel</Button>
```

Call `closeSidePanel` explicitly:
- In a cancel button handler.
- In an `onSuccess` callback after a successful mutation.

The panel also closes automatically when:
- The URL changes (any route navigation — `pathname`, `search`, or `hash`).
- The user presses Escape.

---

## Panel Sizes

| Size | When to use |
|---|---|
| `regular` | Default — standard add/edit forms |
| `wide` | Complex forms with multiple sections |
| `large` | Full-width content, data-heavy panels |

Pass `size` in `openSidePanel` to set it at open time:

```tsx
openSidePanel({ component: EditPool, title: "Edit pool", size: "wide" });
```

Change the size after the panel is already open:

```tsx
const { setSidePanelSize } = useSidePanel();

setSidePanelSize("large");
```

`SidePanel` resets the size to `"regular"` automatically when it unmounts.

---

## Testing Side Panels

`mockSidePanel` is exported from `@/testing/utils`. It must be called with `await` at the top level of the module (outside `describe`).

### Asserting a panel opens

```tsx
import { AddPool } from "@/app/pools/components";
import PoolsListHeader from "@/app/pools/components/PoolsListHeader/PoolsListHeader";
import { mockSidePanel, renderWithProviders, screen, userEvent } from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("PoolsListHeader", () => {
  it("opens the Add pool panel when the button is clicked", async () => {
    renderWithProviders(<PoolsListHeader />);

    await userEvent.click(screen.getByRole("button", { name: "Add pool" }));

    expect(mockOpen).toHaveBeenCalled();
  });
});
```

To assert on the specific arguments:

```tsx
expect(mockOpen).toHaveBeenCalledWith(
  expect.objectContaining({ component: AddPool, title: "Add pool" })
);
```

### Asserting a panel closes

```tsx
import DeletePool from "./DeletePool";
import { mockSidePanel, renderWithProviders, screen, userEvent, waitForLoading } from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("DeletePool", () => {
  it("closes the panel when Cancel is clicked", async () => {
    renderWithProviders(<DeletePool id={2} />);
    await waitForLoading();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(mockClose).toHaveBeenCalled();
  });
});
```

---

## Dos and Don'ts

**Do** pass the component class to `openSidePanel`.

```tsx
openSidePanel({ component: AddPool, title: "Add pool" });
```

**Don't** pass a JSX element.

```tsx
openSidePanel({ component: <AddPool />, title: "Add pool" });
```

---

**Do** call `closeSidePanel` on cancel and after a successful mutation.

```tsx
const { closeSidePanel } = useSidePanel();
<Button onClick={closeSidePanel}>Cancel</Button>
```

**Don't** leave the panel open after an action completes.

---

**Do** use `mockSidePanel` to verify open/close behaviour in tests.

```tsx
const { mockOpen, mockClose } = await mockSidePanel();
```

**Don't** mock `useSidePanel` manually in individual tests.

---

**Do** use `setSidePanelSize` to change the size dynamically when the content requires it.

```tsx
setSidePanelSize("wide");
```

**Don't** render separate panels or mount `<SidePanel />` directly in feature components.

---

**Do** call `await mockSidePanel()` at module level, outside any `describe` or `it` block.

```tsx
const { mockOpen } = await mockSidePanel();

describe("MyComponent", () => { ... });
```

**Don't** call `mockSidePanel()` inside a `beforeEach` or a test body — it registers its own `beforeEach` internally and must run at the top level.

---

**Do** compose all panel content inside a single component passed to `openSidePanel`.

**Don't** render multiple root elements as the panel body — wrap them in one component.
