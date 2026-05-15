# Testing Best Practices

## Unit Tests

## TL;DR

- Run tests using `yarn test path/to/file.test.tsx`, add `--run` to only run once instead of watching
- Import all test utilities from `@/testing/utils` (includes `renderWithProviders`, `screen`, `waitFor`, `userEvent`, `within`, etc.)
- Use `renderWithProviders` for all modern component tests
- Use `setupMockServer` to configure MSW for API mocking
- Use `renderHookWithProviders` for testing custom hooks
- Use `mockSidePanel` to mock side panel context
- Use `mockIsPending` to mock loading states
- Organize tests with `describe` blocks for display, validation, permissions, and actions
- Use `waitFor` for async assertions
- Use `userEvent` for simulating user interactions
- Legacy tests may use `configureStore()` for Redux state - consider these outdated

## Overview

We use [Vitest](https://vitest.dev/) as our test runner and [React Testing Library](https://testing-library.com/react) for component testing. API mocking is handled by [MSW (Mock Service Worker)](https://mswjs.io/).

**Important**: All testing utilities should be imported from `@/testing/utils`, which re-exports common utilities from Testing Library (`screen`, `waitFor`, `within`, `userEvent`) along with our custom testing helpers (`renderWithProviders`, `setupMockServer`, `mockSidePanel`, etc.). This ensures consistency across the codebase.

## Modern Testing Patterns

### Component Tests with `renderWithProviders`

`renderWithProviders` is the standard way to render components in tests. It provides all necessary context providers (React Query, Redux, Router, WebSocket, Side Panel), eliminating the need to manually wrap components in providers. This ensures your tests run in an environment that closely mirrors your application's runtime context.

```typescript
describe("MyComponent", () => {
  it("renders correctly", async () => {
    renderWithProviders(<MyComponent />);

    await waitFor(() => {
      expect(screen.getByText("Hello World")).toBeInTheDocument();
    });
  });
});
```

### Setting Up Mock Server

Use `setupMockServer` at the top of your test file to configure MSW handlers. This function handles the complete lifecycle of the mock server.

```typescript
const mockServer = setupMockServer(
  usersResolvers.listUsers.handler(),
  usersResolvers.createUser.handler()
);

describe("MyComponent", () => {
  it("displays users", async () => {
    renderWithProviders(<MyComponent />);
    // Test implementation
  });
});
```

The `setupMockServer` function:

- Automatically sets up and tears down the mock server
- Resets handlers between tests
- Accepts any number of request handlers

### Overriding Mock Responses

Override default mock responses using `mockServer.use()`. This allows you to customize API responses for specific test cases, enabling you to test error states, empty states, and edge cases without modifying your resolver files.

```typescript
it("handles empty state", async () => {
  mockServer.use(usersResolvers.listUsers.handler({ items: [], total: 0 }));
  renderWithProviders(<MyComponent />);

  await waitFor(() => {
    expect(screen.getByText("No users found")).toBeInTheDocument();
  });
});

it("handles errors", async () => {
  mockServer.use(
    usersResolvers.listUsers.error({
      message: "Failed to load users",
      code: 500,
      kind: "Error",
    })
  );
  renderWithProviders(<MyComponent />);

  await waitFor(() => {
    expect(screen.getByText("Failed to load users")).toBeInTheDocument();
  });
});
```

### Testing with Custom State

Pass custom Redux state to `renderWithProviders` to test components in specific application states. This is useful for testing permission-based UI, user-specific content, or any component behavior that depends on Redux state.

```typescript
it("displays user-specific content", () => {
  renderWithProviders(<MyComponent />, {
    state: {
      user: factory.userState({
        auth: factory.authState({
          user: factory.user({ username: "admin" }),
        }),
      }),
    },
  });

  expect(screen.getByText("Welcome, admin")).toBeInTheDocument();
});
```

### Testing Hooks

Use `renderHookWithProviders` to test custom hooks in isolation. This wrapper provides all necessary context (React Query, Redux, WebSocket) that your hooks might depend on, allowing you to test hook logic independently from components.

```typescript
const mockServer = setupMockServer(usersResolvers.listUsers.handler());

describe("useUsers", () => {
  it("returns users data", async () => {
    const { result } = renderHookWithProviders(() => useUsers());

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockUsers);
  });
});
```

### Mocking Loading States

Use `mockIsPending` to test loading states without waiting for actual API calls. This utility mocks React Query's `useQuery` to return a pending state, allowing you to verify that your loading UI renders correctly.

```typescript
it("displays loading state", async () => {
  mockIsPending();
  renderWithProviders(<MyComponent />);

  await waitFor(() => {
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});
```

### Mocking Side Panel

Use `mockSidePanel` to mock side panel interactions and verify that your components correctly open and close side panels with the expected content and properties.

```typescript
const { mockOpen, mockClose } = await mockSidePanel();

describe("MyComponent", () => {
  it("opens side panel when button clicked", async () => {
    renderWithProviders(<MyComponent />);

    await userEvent.click(screen.getByRole("button", { name: /add user/i }));

    expect(mockOpen).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Add user",
      })
    );
  });

  it("closes side panel on cancel", async () => {
    renderWithProviders(<MyForm />);

    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(mockClose).toHaveBeenCalled();
  });
});
```

## Test Structure

### Organize with `describe` Blocks

Always organize tests into logical groups using `describe` blocks. This improves test readability, makes it easier to locate specific tests, and provides better structure in test output.

```typescript
describe("MyComponent", () => {
  describe("display", () => {
    it("renders loading state", () => {});
    it("renders empty state", () => {});
    it("renders data correctly", () => {});
  });

  describe("validation", () => {
    it("shows error for invalid input", () => {});
    it("prevents submission with errors", () => {});
  });

  describe("permissions", () => {
    it("disables buttons without permissions", () => {});
    it("enables buttons with permissions", () => {});
  });

  describe("actions", () => {
    it("submits form on save", () => {});
    it("closes on cancel", () => {});
  });
});
```

## Common Testing Patterns

### User Interactions

Use `userEvent` for simulating user actions. This library provides more realistic user interactions than the legacy `fireEvent` API, including proper focus management and keyboard event sequences.

```typescript
// Clicking buttons
await userEvent.click(screen.getByRole("button", { name: /save/i }));

// Typing in text fields
await userEvent.type(
  screen.getByRole("textbox", { name: /username/i }),
  "testuser"
);

// Selecting options
await userEvent.selectOptions(
  screen.getByRole("combobox", { name: /role/i }),
  "admin"
);

// Checking checkboxes
await userEvent.click(screen.getByRole("checkbox", { name: /accept/i }));
```

### Querying Elements

Use semantic queries from `screen` to find elements in your tests. Prioritize queries that reflect how users interact with your application (by role, label, or text) rather than implementation details like test IDs.

```typescript
// By role (preferred)
screen.getByRole("button", { name: /submit/i });
screen.getByRole("textbox", { name: /email/i });
screen.getByRole("heading", { name: /welcome/i });

// By label text
screen.getByLabelText("Username");
screen.getByLabelText(/password/i);

// By text content
screen.getByText("Hello World");
screen.getByText(/loading/i);

// By test ID (use sparingly)
screen.getByTestId("custom-element");

// Query variants
screen.queryByRole("button"); // Returns null if not found
screen.findByRole("button"); // Returns promise, waits for element
```

### Async Assertions

Always use `waitFor` for async assertions to handle asynchronous state updates, API calls, and DOM changes. Never use arbitrary timeouts or delays in tests.

```typescript
// Wait for element to appear
await waitFor(() => {
  expect(screen.getByText("Success")).toBeInTheDocument();
});

// Wait for element to disappear
await waitFor(() => {
  expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
});

// Wait for hook to resolve
await waitFor(() => {
  expect(result.current.isSuccess).toBe(true);
});
```

### Testing Within Specific Elements

Use `within` to query inside a specific element, which is particularly useful for testing table rows, list items, or any nested content where you need to scope your queries.

```typescript
const row = screen.getByRole("row", { name: /john doe/i });
expect(within(row).getByText("admin")).toBeInTheDocument();
expect(within(row).getByRole("button", { name: /edit/i })).toBeInTheDocument();
```

### Checking Resolver Calls

Verify that API calls were made by checking the `resolved` flag on your mock resolvers. This is useful for confirming that form submissions or user actions trigger the expected API requests.

```typescript
await userEvent.click(screen.getByRole("button", { name: /save/i }));

await waitFor(() => {
  expect(usersResolvers.createUser.resolved).toBeTruthy();
});
```

## Legacy Patterns (Avoid in New Code)

### Using `configureStore()` Directly

Legacy tests may create Redux stores manually using `configureStore()` from `redux-mock-store`. This pattern predates our modern testing utilities and should be avoided in new code. Instead, pass state directly to `renderWithProviders`.

```typescript
// ❌ Legacy pattern - avoid in new code
const mockStore = configureStore();
const store = mockStore(factory.rootState());

// ✅ Modern pattern - use renderWithProviders instead
renderWithProviders(<MyComponent />, {
  state: factory.rootState(),
});
```

## Common Pitfalls

- **Don't** forget to use `await` with `userEvent` methods
- **Don't** forget to use `waitFor` for async assertions
- **Don't** query elements that should not exist with `getBy*` - use `queryBy*` instead
- **Don't** test implementation details - test what users see and do
- **Don't** forget to set up mock server handlers before tests
- **Don't** use `configureStore()` directly in new tests - use `renderWithProviders`
- **Don't** mock components or hooks - mock at the network layer with MSW
- **Don't** forget to reset mock functions between tests (handled automatically by `setupMockServer`)
- **Don't** use `getByTestId` unless absolutely necessary - prefer semantic queries

## Debugging Tests

### View Rendered Output

Use `screen.debug()` to print the current DOM structure when debugging test failures. This helps you understand what's actually rendered versus what you expect.

```typescript
// Print the current DOM
screen.debug();

// Print a specific element
screen.debug(screen.getByRole("button"));
```

### Check Available Queries

```typescript
// See all available roles
screen.logTestingPlaygroundURL();
```

### View Network Requests

MSW will warn you if an unhandled request is detected, which helps identify missing mock handlers. For more detailed request logging, you can add custom logging to your mock resolvers or use MSW's debugging features.

## Factories

Factories live in `src/testing/factories/`, one file per model. All factories are exported from `src/testing/factories/index.ts`.

### New factories — fishery

Use `fishery` for all new factories. Three supporting libraries are available:
- `fishery` — `Factory.define()` creates the factory; `sequence` auto-increments per build call.
- `unique-names-generator` — generates readable fake names for models displayed in lists.
- `chance` — generates realistic random data (URLs, GUIDs, booleans, etc.). Seed with `sequence` for deterministic output.

```ts
import Chance from "chance";
import { Factory } from "fishery";
import { adjectives, animals, uniqueNamesGenerator } from "unique-names-generator";

import type { RackWithSummaryResponse } from "@/app/apiclient";

export const rackFactory = Factory.define<RackWithSummaryResponse>(({ sequence }) => {
  const chance = new Chance(`maas-${sequence}`);
  const name = uniqueNamesGenerator({
    dictionaries: [adjectives, animals],
    separator: "_",
    style: "lowerCase",
    seed: sequence,
  });
  return {
    id: sequence,
    name,
    registered_agents_system_ids: [chance.guid()],
  };
});
```

Using a fishery factory in tests:

```ts
import { rackFactory } from "@/testing/factories/racks";

const rack = rackFactory.build();
const namedRack = rackFactory.build({ name: "my-rack" });
const racks = rackFactory.buildList(3);
```

### Legacy factories — cooky-cutter

Older factories use `cooky-cutter`. Do not add new factories with `cooky-cutter` — all new factories use fishery. Existing cooky-cutter factories are being migrated over time.

Legacy factories are called as functions via the `factory` namespace:

```ts
import { factory } from "@/testing/factories";

const pool = factory.resourcePool({ name: "production" });
```

### When to add a new factory

Any time a test needs a typed mock object that does not have a factory yet. Add a fishery factory to the appropriate file in `src/testing/factories/` and export it from `index.ts`. Never hand-craft raw object literals in tests.

## Resolvers

Resolvers live in `src/testing/resolvers/<domain>.ts`. The full authoring guide is in `api-hooks.md` — this section covers consuming resolvers in tests.

```ts
const mockServer = setupMockServer(poolsResolvers.listPools.handler());

mockServer.use(poolsResolvers.listPools.handler({ items: [], total: 0 }));

mockServer.use(poolsResolvers.deletePool.error());

await waitFor(() => {
  expect(poolsResolvers.createPool.resolved).toBeTruthy();
});
```

## E2E Tests

Stack: Cypress with `@badeball/cypress-cucumber-preprocessor`. Gherkin `.feature` files describe scenarios; TypeScript `.steps.ts` files implement them. Do not use Playwright for new E2E tests — it is only used for documentation link-checking in this project.

Directory layout:

```
cypress/
├── e2e/
│   └── with-users/
│       └── features/
│           └── <domain>/
│               └── <feature>.feature
├── support/
│   └── step_definitions/
│       ├── common/
│       │   ├── auth.steps.ts
│       │   ├── navigation.steps.ts
│       │   └── actions.steps.ts
│       └── <domain>/
│           └── <feature>.steps.ts
```

Writing a feature file:

```gherkin
Feature: DNS record assignment

  Background:
    Given the user is logged in

  Scenario: Create DNS record from a device IP and follow link to device details
    Given the user navigates to the domains page
    When the DNS default domain row is opened
    And the user clicks the "Add record" button
    And the user enters a record name
    And the user submits the form
    Then the record name should appear as a link in the DNS record list
```

Writing step definitions:

```ts
import { When, Then } from "@badeball/cypress-cucumber-preprocessor";

When("the DNS default domain row is opened", () => {
  cy.findByRole("grid", { name: "Domains table" }).within(() => {
    cy.get("[data-testid='domain-name']").first().click();
  });
});

Then("the record name should appear as a link in the DNS record list", () => {
  cy.findByRole("link", { name: /my-record/i }).should("exist");
});
```

Running E2E tests:

```bash
yarn cypress open
yarn cypress run
```

## Avoiding Step Duplication in E2E Tests

**Use `Background` for shared setup.** Steps shared by all scenarios in a feature file go in `Background`, not repeated in every `Scenario`.

**Use common step definitions for cross-domain steps.** Generic steps live in `cypress/support/step_definitions/common/` and are available to all feature files with no import required.

**Extract repeated command sequences into helpers:**

```ts
export const completeAddMachineForm = () => {
  cy.waitForPageToLoad();
  cy.waitForTableToLoad({ name: /Machines/i });
  cy.findByRole("button", { name: "Add hardware" }).click();
  cy.get(".p-contextual-menu__link").contains("Machine").click();
};
```

**Parametrise steps instead of duplicating them:**

```ts
When("the user clicks the {string} button", (button: string) => {
  cy.findByRole("button", { name: button }).click();
});

When("the user clicks the button matching {string}", (button: string) => {
  cy.findByRole("button", { name: new RegExp(button, "i") }).click();
});
```

Dos and Don'ts:
- **Do** put reused auth and navigation steps in `common/`.
- **Do** use `Background` for setup shared across all scenarios.
- **Do** extract repeated sequences into `*.helpers.ts`.
- **Don't** copy-paste step implementations.
- **Don't** put domain-specific steps in `common/`.
