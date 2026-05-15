# agents.md — maas-ui

## Codebase description

maas-ui is the React/TypeScript web frontend for MAAS (Metal as a Service), an
open-source tool for discovering, commissioning, and deploying bare-metal
servers. It is a Vite-based single-page application written in strict
TypeScript. The UI communicates with the MAAS backend over REST (via TanStack
Query) and WebSockets (via Redux-Saga). Redux is actively being migrated out —
TanStack Query is the preferred approach for all new REST endpoints. Redux-Saga
handles WebSocket messaging and still contains some legacy REST flows (e.g.
login, licence keys); do not add new REST calls there.

## Tech stack

- React 19, TypeScript (strict), Vite
- TanStack Query + Hey API OpenAPI codegen (`src/app/apiclient/`) — new standard
- Redux Toolkit + Redux-Saga — legacy, being phased out
- Formik (`FormikForm`, `FormikField`) for forms; Yup for validation
- @canonical/react-components and @canonical/maas-react-components (Vanilla UI)
- Vitest + React Testing Library (unit/integration)
- MSW (Mock Service Worker) for API mocking in tests
- Cypress + Cucumber (E2E) — Playwright is only used for documentation link checking; do not use it for new E2E tests

## Dos

- Use TanStack Query hooks in `src/app/api/query/` for any new REST endpoint —
  never Redux
- Wrap queries with `useWebsocketAwareQuery` + `queryOptionsWithHeaders`; when
   a mutation changes cached server state, invalidate the relevant query keys in
   `onSuccess`
- Use `mutationOptionsWithHeaders` (not bare `useMutation`) so response headers
  are included
- Create MSW mock resolvers in `src/testing/resolvers/` and use
  `renderWithProviders` / `renderHookWithProviders` in all component/hook tests
- Write function components only; use hooks for state and side effects
- Place views in `<domain>/views/`, domain-shared components in
  `<domain>/components/`, app-wide shared components in `src/app/base/components/`
- Use `FormikForm` + `FormikField` for forms; `ModelActionForm` for simple
  confirmation dialogs; Yup for all validation schemas
- Query elements by accessible role/label/text (Testing Library best practices);
  use `userEvent` for interactions and `waitFor` for async assertions
- Run `yarn lint` and `yarn test` before finishing the task; all tests must pass and no lint errors should remain; 

## Don'ts

- Don't add new Redux slices, sagas, or actions — Redux is being phased out
- Don't add a new REST endpoint to Redux-Saga — only WebSocket messaging goes
  through sagas
- Don't edit `src/app/apiclient/` directly — it is auto-generated from the
  OpenAPI spec via `yarn generate-api-client`
- Don't write class components
- Don't use `data-testid` in new code — use accessible semantic queries instead
  (`getByRole`, `getByLabelText`, etc.)
- Don't use `any` — use `TSFixMe` (importable from `@/app/base/types`) only as a
  last resort and leave a comment flagging it for future fixing
- Don't use `configureStore()` from `redux-mock-store` in new tests — pass
  state via `renderWithProviders` instead and if you need to check actions in the store then `renderWithProviders` returns the store for this purpose
