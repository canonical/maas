# Component Standards

Developer reference for the maas-ui codebase. Each document covers one area of the stack — where things live, how to write them, and how to test them.

---

## Table of Contents

| Document | What it covers |
|---|---|
| [Architecture](architecture.md) | Directory structure, component elevation path, standard view layout, hooks conventions, API layer split, and tech stack |
| [Routing](routing.md) | Single router definition, per-domain URL files, `argPath`, `getRelativeRoute`, lazy loading, and error boundaries |
| [Styling](styling.md) | Global SCSS entry point, per-component `_index.scss` mixins, Vanilla Framework usage, and encapsulation rules |
| [Store Management](store-management.md) | Redux scope (legacy only), reading from the store, `useFetchActions`, testing with `renderWithProviders`, and migration path to TanStack Query |
| [API Hooks](api-hooks.md) | TanStack Query hook authoring, naming conventions, `useWebsocketAwareQuery`, mutations, MSW resolvers, and common pitfalls |
| [Forms](forms.md) | `FormikForm`, `ModelActionForm`, Yup validation, `onSuccess`/`closeSidePanel`, API error display, and form testing patterns |
| [Tables](tables.md) | `GenericTable`, column definition hooks, pagination, `TableActions`, row click vs action columns, and table testing patterns |
| [Side Panels](side-panels.md) | `useSidePanel`, opening with typed props, closing, size options, auto-close behaviour, and `mockSidePanel` testing |
| [Notifications](notifications.md) | Backend-driven notification flow, category-to-toast mapping, `useDismissNotification`, and what feature code should not do |
| [Permissions](permissions.md) | Two-layer permissions (`is_superuser` and `permissions[]`), `useCanEdit` for node resources, and testing both layers |
| [Constants](constants.md) | Three-level hierarchy (app / domain / view), `as const` arrays, enums, `Record` label maps, and navigation constants |
| [Testing](testing.md) | Unit tests, factories, MSW resolvers, Cypress E2E with Cucumber, and avoiding step duplication |

---

## Quick Orientation

**Starting a new feature?** Read [Architecture](architecture.md) first, then [Routing](routing.md) to wire up the new view.

**Adding an API endpoint?** See [API Hooks](api-hooks.md) for the full authoring guide. If the data needs to drive a form, see [Forms](forms.md). If it needs real-time updates, the WebSocket-aware query pattern is in [API Hooks](api-hooks.md#websocket-aware-queries).

**Writing tests?** [Testing](testing.md) covers factories, resolvers, and E2E. Side panel open/close assertions are in [Side Panels](side-panels.md#testing-side-panels).

**Unsure whether to use Redux or TanStack Query?** See [Store Management](store-management.md).