# MAAS UI

## Contents

- [Project conventions](#project-conventions)
  - [Usability](#usability)
  - [Code style](#code-style)
  - [React components](#react-components)
- [Code structure](#code-structure)
- [React](#react)
  - [Hooks](#hooks)
  - [Components](#components)
    - [Forms](#forms)
  - [Vanilla components](#vanilla-components)
  - [Redux](#redux)
    - [Redux Toolkit](#redux-toolkit)
    - [Reselect](#reselect)
    - [Redux-Saga](#redux-saga)
  - [TypeScript](#typeScript)
    - [TSFixMe](#tsfixme)
  - [Testing](#testing)
    - [Test attributes (OUTDATED)](#test-attributes)
    - [Model factories](#model-factories)
  - [Coding style](#coding-style)
    - [ES6](#es6)
    - [Prettier](#prettier)
- [Proxy](#proxy)
- [End-to-end](#end-to-end)
  - [Cypress](#cypress)
  - [Playwright](#playwright)

## Project conventions

### Usability

Our unofficial policy on responsive design in MAAS-UI is that everything should be clearly visible on all screen sizes, but it doesn't necessarily have to be the most visually appealing on small screens.
Only a small percentage of users interact with the MAAS client on mobile devices, but it's not uncommon for people to use it on one half of their monitor viewport.

### Code style

Prioritize clear, self-explanatory code, and only use JSDoc to provide context or additional information that cannot be inferred from the code itself.

### React Components

We encourage [component-driven](https://www.componentdriven.org/) development, and use of [Storybook](https://storybook.js.org/) for interactive documentation.

Follow the presentational and container components pattern where appropriate. Read more on good component design in the  [React documentation](https://reactjs.org/docs/thinking-in-react.html#step-3-identify-the-minimal-but-complete-representation-of-ui-state).

When developing new features or extending existing ones, consider the following:

- Think of all the variations of a UI component and how each can be represented using props.
- Prefer a single `variant` prop for representing visual variations of a component.

```tsx
<Button variant="primary" />
```

- Create stories for each variant in [Storybook](https://storybook.js.org/).
- Add state management, side effects, and application-specific logic into container component passing the state as props to the presentational component.

## Code structure

The high-level interactions between the React side of the frontend and the API are illustrated below.

> NOTE: MAAS-UI currently utilises both REST and web socket API through TanStack Query and Redux, respectively.

![code-structure](https://github.com/user-attachments/assets/d7abb957-f5f7-453d-9dab-a1ff749a222d)

## React

### Vite

MAAS UI is bootstrapped with [Vite](https://vitejs.dev/). The main features that MAAS UI uses are:

 - Hot module replacement
 - [Manual chunks](https://github.com/canonical/maas-ui/blob/main/vite.config.ts#L7-L12) at build time
 - Native ES modules
 - Lazy-loading / route-based code splitting

### Hooks

We use React >v18.0.0 which has support for [React hooks](https://reactjs.org/docs/hooks-intro.html). While it’s still possible to write components using the class syntax, all new components should be function components that use state hooks where appropriate.

### Components

Components should be created with TypeScript and MAAS-UI does not use class components, instead it uses function components.

The app directories are split by top level nav items e.g. /machines corresponds to \`[app/machines](https://github.com/canonical-web-and-design/maas-ui/tree/master/ui/src/app/machines)\`. Components that are reusable or shared between pages live in \`[app/base](https://github.com/canonical-web-and-design/maas-ui/tree/master/ui/src/app/base)\`.

Each of these directories contain a `./components` and `./views` directory.

Views are components that relate to a sub url (e.g. /machine/:id would point to [app/machines/views/MachineDetails](https://github.com/canonical-web-and-design/maas-ui/tree/master/ui/src/app/machines/views/MachineDetails)). Contained within the view directories are any additional components, forms etc. related to the view.

Components that are shared between multiple views (within the same top level route) live in `./components`. Consider if that component might be used by other areas of the app, and if it will then it should live in \`[app/base/components](https://github.com/canonical-web-and-design/maas-ui/tree/master/ui/src/app/base/components)\`.

#### Forms

We use a set of components, such as FormikForm, FormikField for building forms which are built on top of [Formik](https://github.com/jaredpalmer/formik).

### Vanilla components

Many of the Vanilla components have React implementations which you can find in the [react-components](https://github.com/canonical-web-and-design/react-components/) project. There are [online docs](https://canonical-web-and-design.github.io/react-components/) for these components.

If you need a vanilla component that does not already exist, first implement it in MAAS-UI and then propose it to the react-components repo.

### TanStack Query

We use [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview) for our API functions used to interact with the backend. React Query acts as our data fetching and posting tool, allowing for a single-form communication structure for all endpoints, and providing a query cache. The query cache serves to alleviate the load of numerous API calls by storing the responses and only requesting new data if said cache is marked as stale.

In addition to TanStack Query, we also use [Hey API](https://heyapi.dev) as our codegen for creating the aforementioned API functions from an OpenAPI spec document. Hey API's generated files, contained in \`[app/apiclient](https://github.com/canonical/maas-ui/tree/main/src/app/apiclient)\`, allow us to accurately update our data types and API calls according to the most recent specification provided. The generated SDK functions are wrapped by custom query functions found in \`[app/api/query](https://github.com/canonical/maas-ui/tree/main/src/app/api/query)\`, manually written to correspond to each endpoint.

#### Typical Query Function

A typical query function is simply a call to its corresponding SDK function with provided types and exposed options, wrapped in a custom web socket hook we use to allow for invalidating the query cache through messages pushed by the back-end. In the case where the query affects the data being displayed, the query function also invalidates the cache upon success to execute a fetch of the newly modified data.

```ts
export const useCreateZone = (mutationOptions?: Options<CreateZoneData>) => {
  const queryClient = useQueryClient();
  return useMutation<
    CreateZoneResponse,
    CreateZoneError,
    Options<CreateZoneData>
  >({
    ...createZoneMutation(mutationOptions),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: listZonesQueryKey(),
      });
    },
  });
};
```

### Redux

> NOTE: MAAS-UI will be completely migrating to TanStack Query for its API structure, and phase out the use of Redux. This transition is being carried out by migrating each endpoint separately, and removing the migrated types from the Redux store.

We use [Redux](https://redux.js.org/introduction/getting-started) as our state-management tool. To put it briefly, Redux is responsible for storing all the app-wide state (in the “store”) and provides a predictable methodology for changing that state. The normal flow is this: an action is dispatched, and as a consequence, some state is changed via a reducer function. Actions can be dispatched directly by the user from the UI, or elsewhere (e.g. a server).

![redux](https://user-images.githubusercontent.com/47540149/214085476-46535bee-cc9d-407e-a569-90014ab7f7b2.png)

We also use some libraries/middleware to help with certain functions:

- [Redux Toolkit](https://redux-toolkit.js.org/), for reducing the boilerplate that usually comes with Redux projects.
- [Reselect](https://github.com/reduxjs/reselect), for computing and retrieving derived data from the Redux store.
- [Redux-Saga](https://redux-saga.js.org/), for handling actions which lead to side effects (e.g. async API calls).

#### Slice structure

Most Redux slices have a similar structure when it comes to storing data received from the server. However, the `state.machine` slice is an exception. This is because, unlike other models which are filtered on the front-end, machine list filtering is handled on the server.

##### Typical slice

A typical slice contains:

- An `items` property for storing the list of all items of a particular model
- Associated `loading`, `loaded`, and `errors` properties

```
controller: {
  items: Controller[],
  loading: boolean,
  loaded: boolean,
  errors: [],
  [...]
}
```

##### state.machine slice

The state slice for the `machine` model includes additional properties: `lists`, `counts`, and `filters`.

- Requested data is stored in `machine.lists` and `machine.counts`
- Data is indexed by a unique identifier based on request parameters
- Filters supported by the server are stored in `machine.filters`
- `machine.lists` contains machine IDs for each request, referencing data in `machine.items`

```
machine: {
  items: Machine[];
  lists: { [query: string]: Machine["system_id"][] };
  counts: { [query: string]: number };
  filters: { [filter]: string };
  [...]
}
```

#### Redux Toolkit

MAAS-UI uses [Redux Toolkit](https://redux-toolkit.js.org/) to create actions and reducers for each MAAS model.

The [store directory](https://github.com/canonical-web-and-design/maas-ui/tree/master/ui/src/app/store) (roughly) follows the [“ducks” pattern](https://github.com/erikras/ducks-modular-redux) so that everything for a model (actions, reducers, selectors, types and utils) are together. The folder names in the store directory correspond to a model’s name as given in the websocket handlers, which is also used to name each “slice” (top level key) of the Redux state. Slices are set up in each model’s slice.ts files using [createSlice](https://redux-toolkit.js.org/api/createSlice), which defines the actions and reducers for the model.

For example, the directory at [ui/src/app/store/subnet](https://github.com/canonical-web-and-design/maas-ui/tree/master/ui/src/app/store/subnet) contains the slice for the subnet model (which defines the subnet action creators and reducers), the subnet selectors, types for the subnet model itself as well as the actions, and any utils that are intrinsically tied to the subnet model. The subnet reducers reduce the state in rootState.subnet, and the websocket methods should all be prefixed with “subnet”.

#### Reselect

When data needs to be retrieved from the store it is done through a selector. These selectors are created with [Reselect](https://github.com/reduxjs/reselect) and live within the model’s directory in the [store](https://github.com/canonical-web-and-design/maas-ui/tree/master/ui/src/app/store).

#### Redux-Saga

Redux-Saga acts as middleware between actions and reducers, allowing Redux actions to be understood by the MAAS server, and MAAS server responses to be understood by Redux. We use Redux-Saga for all of our asynchronous (HTTP and websocket) calls.

A common flow in MAAS UI is this: an action is dispatched from a component to fetch some data, a saga intercepts that action and transforms it into a websocket message to send to the MAAS server, the saga waits until the server responds and then dispatches an action based on the response (e.g. data or error message).

The saga files can be found in [ui/src/app/base/sagas](https://github.com/canonical-web-and-design/maas-ui/tree/master/ui/src/app/base/sagas).

![redux-saga](https://user-images.githubusercontent.com/47540149/214086167-45b4b87a-b71d-400f-93d1-997d99681fd9.png)

- `yield*call(func, ...args)` is used to call a function with the provided arguments,
- `yield* put(action)` is used to dispatch an action to the Redux store,
- `yield*take(actionType)` is used to pause the generator function until an action with the provided type is dispatched,
- `yield* takeLatest(actionType, func)`  starts the provided function when an action with the provided type is dispatched, but if there was a previously started func still running, it gets cancelled.

#### Redux-Saga flow in maas-ui

##### rootSaga

`rootSaga` is the entry point of our saga workflows. It's a generator function, denoted by the function*syntax. yield* all([]) is used to initiate all the sagas simultaneously. Each saga inside the array is watching for specific action types to be dispatched, and when that happens, they run specific tasks.

##### handleMessage

The `handleMessage` saga is responsible for handling incoming WebSocket messages. It's an infinite loop that keeps running and waits for incoming WebSocket messages. When a message arrives, it checks the type of the event and based on that dispatches different actions using yield* put(action).

##### sendMessage

The `sendMessage` function handles sending WebSocket messages. It first dispatches an action that a particular request has started, sends the message, and handles any potential errors by dispatching an error action if needed. Here, `yield* call(func, ...args)` is used to call a function with the provided arguments and wait for it to finish before moving to the next instruction.

##### setupWebSocket and watchWebSockets

`setupWebSocket` and `watchWebSockets` are used for setting up and managing the WebSocket connection. When the WebSocket connection is requested (status/websocketConnect action is dispatched), watchWebSockets calls setupWebSocket. Inside setupWebSocket, it tries to create a WebSocket connection and then sets up several watchers inside a race block, which means it's waiting for either these watchers to finish or for the status/websocketDisconnect action to be dispatched.

### TypeScript

maas-ui built with TypeScript in strict mode. Any new modules in should be written in [TypeScript](https://www.typescriptlang.org/).

#### TSFixMe

There may occasionally be times where you can’t type something. In those cases you might be able to use \`any\` to handle all types. However, our linter will not let you use \`any\` directly.

We have an alias of \`any\` named: \`TSFixMe\` that you can use (it can be imported from `app/base/types`), this also helps us to recognise this is a type that needs updating in the future.

You should avoid using \`TSFixMe\` unless you really get stuck.

### Testing

As a general rule, we concentrate on user-centric testing and avoid testing implementation details. For that reason usage of test attributes such as `data-testid` should be avoided. Any occurrence of such will usually be for historical reasons.

#### Vitest and testing-library

We use [Vitest](https://vitest.dev/) for unit and integration tests (`.test.tsx` files). Vitest is the native testing framework for Vite. Its API is (mostly) a drop-in replacement for Jest, which we used in the past.

When running these tests Vitest enters the "watch" mode by default - as soon as file changes are detected, the test(s) will automatically re-run.

[React Testing Library](https://testing-library.com/docs/) is our primary tool for testing React components. It encourages testing user interactions rather than implementation details (internal component state, component lifecycle functions etc.).

To this end, it renders the React code into actual DOM nodes, as opposed to libraries like Enzyme (the previous standard for testing React) which render the React DOM. Components should be accessed through accessible attributes such as roles, names, and labels.

#### Testing utility functions

Many of our tests require providers for the Redux store and the React router. We provide a utility function that automatically wraps the code you want to render called `renderWithProviders`

You can directly pass `state` as an option to both of these functions, and a mock store will be created internally and provided to the rendered components.

You can see the full suite in the [test utils file on GitHub](https://github.com/canonical/maas-ui/blob/main/src/testing/utils.tsx).

#### Test attributes

**Note: This is an OUTDATED practice**

It is very easy to write a component test that is too general or too specific with its component selectors. Both of these cases result in fragile tests. To this end MAAS-UI uses `data-testid` attributes to provide a convenient method of finding a component.

The attribute can be applied to any component or element:

```html
<Col data-testid="content" size={7}>Content</Col>
```

Which can then be used within a test:

```javascript
expect(wrapper.find("[data-testid='content']").text()).toBe("Content");
```

#### Model factories

To make it easier to interact with the API models and Redux state there are factories for every model and state in [ui/src/testing/factories](https://github.com/canonical-web-and-design/maas-ui/tree/master/ui/src/testing/factories).

Factories can be combined and should only define the states required for a specific test:

```javascript
machineStateFactory({
  items: [machineFactory({ system_id: "abc123" })],
  loading: true,
});
```

### Coding style

There are many helpful tips on the web team’s [practices](https://canonical-web-and-design.github.io/practices/coding/javascript.html) page.

#### ES6

Where possible the es6 style for functions, variables etc. is preferred.

#### Prettier

MAAS-UI uses [Prettier](https://prettier.io/) for formatting. You may wish to set up your IDE to format using Prettier on save.

## Proxy

In production MAAS is served by the region controller and has no support for external authentication to the WebSocket API. To get around this, and to prevent CORS issues, the WebSocket is proxied from a local [Express proxy](https://github.com/canonical-web-and-design/maas-ui/tree/master/proxy) to an external MAAS.

You can [configure](https://github.com/canonical-web-and-design/maas-ui/blob/master/HACKING.md#edit-local-config) which MAAS you want to use with your local UI.

Note: the proxy is only used for local development and plays no part when the UI is served by MAAS.

## End-to-end

### Cypress

Most end-to-end tests are performed using [Cypress](https://www.cypress.io/). The tests are currently minimal, comprising mainly simple smoke tests that check basic functionality. The tests are performed any time a branch on the upstream repo is updated, such as when a forked PR is merged into main.

The Cypress tests run in an Ubuntu VM spun up via GitHub Actions. The relevant MAAS snap is installed on the VM, for example latest/edge in the main branch, and then Cypress tests run against this production version. The primary issue with this approach is that the changes in a PR might not make it into the snap until long after it’s merged, so it’s not until a Cypress test breaks that we can update it to match new changes to the UI. This is something we hope to address soon.

### Playwright

We use [playwright](https://playwright.dev/) for additional end-to-end testing of websocket requests, e.g. in [machines.spec.ts](https://github.com/canonical/maas-ui/blob/main/tests/machines.spec.ts).
