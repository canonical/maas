# Styling

## TL;DR

- Use Vanilla Framework (`p-`, `u-`, `l-` classes) before writing any custom CSS.
- Component styles go in a `_index.scss` file next to the component and are imported directly from the `.tsx` file.
- Write plain SCSS in `_index.scss` — no mixin wrapper required.
- Override Vanilla only in `src/scss/_vanilla-overrides.scss`.
- `@canonical/maas-react-components` CSS is imported globally — do not re-import it.
- Never use inline `style={{}}` except for values that are genuinely computed at runtime.
- The global `src/scss/` directory is for framework-level concerns only — not component styles.
- The SCSS mixin pattern (global `@import` / `@include` registration) is legacy — do not use it for new components.

---

## Technology Overview

- **Vanilla Framework** — Canonical base CSS library. Provides the `p-`, `u-`, and `l-` utility and pattern classes used throughout the UI. Reach for these before writing custom CSS.
- **`@canonical/maas-react-components`** — MAAS-specific component library. Its stylesheet is imported once in `src/scss/index.scss` and available globally.
- **SCSS** — Custom styles are written in SCSS and imported directly from the component file.

---

## Writing Component Styles

### Step-by-step

1. Create `_index.scss` in the same directory as the component file.
2. Write plain SCSS — no mixin wrapper needed:

```scss
.zones-table {
  th,
  td {
    &:is(.machines, .devices, .controllers) {
      text-align: right;
    }
  }
}
```

3. Import the stylesheet from the component's `.tsx` file:

```tsx
import "./_index.scss";
```

That's it. No registration in `src/scss/index.scss` is needed.

### Do

```tsx
import "./_index.scss";

const ZonesTable = () => <div className="zones-table">...</div>;
```

```scss
.zones-table {
  margin-bottom: 0;
}
```

### Don't

```tsx
const ZonesTable = () => (
  <div style={{ marginBottom: 0 }}>...</div>
);
```

---

## Using Vanilla Framework

Use Vanilla Framework classes in JSX before reaching for custom CSS. Use `classNames` for conditional classes.

### Do

```tsx
import classNames from "classnames";

<div className={classNames("p-card", { "is-active": isActive })} />
```

### Don't

```tsx
<div style={{ border: "1px solid #ccc", padding: "1rem" }} />
```

Inline styles bypass Vanilla theming, dark mode, and Vanilla override logic. Only use `style={{}}` for values that are genuinely computed at runtime and cannot be expressed as a static CSS rule.

---

## Overriding Vanilla

All Vanilla Framework overrides go in `src/scss/_vanilla-overrides.scss`. Do not override Vanilla patterns inside component stylesheets.

### Do

```scss
.p-table--expanding__panel {
  padding: 0;
}
```

Place this in `src/scss/_vanilla-overrides.scss`.

### Don't

```scss
.my-component .p-table--expanding__panel {
  padding: 0;
}
```

Cross-cutting Vanilla overrides belong in `_vanilla-overrides.scss` so they apply consistently everywhere the Vanilla class appears.

---

## Legacy: SCSS Mixin Pattern

Older components use a mixin-based pattern where styles are not imported from the `.tsx` file but instead registered globally in `src/scss/index.scss`:

```scss
@import "@/app/base/components/SectionHeader";
@include SectionHeader;
```

The corresponding `_index.scss` wraps all rules in a named mixin:

```scss
@mixin SectionHeader {
  .section-header__title {
    margin: 0;
  }
}
```

This pattern is being phased out. Do not use it for new components. When touching an existing component that uses the mixin pattern, migrating it to the direct import approach is encouraged but not required.

---

## Dos and Don'ts

**Do** use Vanilla Framework classes (`p-`, `u-`, `l-`) before writing custom CSS.

**Don't** duplicate Vanilla styles — check the [Vanilla documentation](https://vanillaframework.io/docs) first.

**Do** import `_index.scss` directly from the component's `.tsx` file.

**Don't** register new component styles in `src/scss/index.scss` via `@import` / `@include`.

**Do** write plain SCSS in `_index.scss` without a mixin wrapper.

**Don't** use inline `style={{}}` for values that can be expressed as CSS.

**Do** put Vanilla overrides in `src/scss/_vanilla-overrides.scss`.

**Don't** place component-specific styles in the global `src/scss/` directory.