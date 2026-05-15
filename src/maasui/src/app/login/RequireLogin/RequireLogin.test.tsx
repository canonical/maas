import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Provider } from "react-redux";
import { createMemoryRouter, RouterProvider } from "react-router";
import configureStore from "redux-mock-store";

import RequireLogin from "./RequireLogin";

import urls from "@/app/base/urls";
import { WebSocketProvider } from "@/app/base/websocket-context";
import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  configState as configStateFactory,
  rootState as rootStateFactory,
  statusState as statusStateFactory,
} from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import { render, screen, setupMockServer, waitFor } from "@/testing/utils";

const mockStore = configureStore();
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, staleTime: Infinity } },
});
const mockServer = setupMockServer(
  authResolvers.getCurrentUser.handler(),
  authResolvers.getMeStatistics.handler()
);

describe("RequireLogin", () => {
  let state: RootState;

  const renderFn = () => {
    const router = createMemoryRouter(
      [
        {
          path: "/login",
          element: <>Login</>,
        },
        {
          element: <RequireLogin />,
          children: [
            {
              path: "/machines",
              element: <>Machines</>,
            },
            {
              path: "/intro/*",
              element: <>Intro</>,
            },
          ],
        },
      ],
      { initialEntries: ["/machines"] }
    );

    const view = render(
      <Provider store={mockStore(state)}>
        <QueryClientProvider client={queryClient}>
          <WebSocketProvider>
            <RouterProvider router={router} />
          </WebSocketProvider>
        </QueryClientProvider>
      </Provider>
    );

    return { view, router };
  };

  beforeEach(() => {
    queryClient.clear();
    state = rootStateFactory({
      status: statusStateFactory({
        authenticating: false,
        authenticated: false,
        connected: true,
        connecting: false,
        error: undefined,
      }),
      config: configStateFactory({
        loaded: true,
      }),
    });
  });

  it("redirects to /login if not authenticated", async () => {
    const { router } = renderFn();

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/login");
    });
  });

  it("includes the initial route as a query parameter for redirecting after login", async () => {
    const { router } = renderFn();

    await waitFor(() => {
      expect(router.state.location.search).toBe("?redirectTo=%2Fmachines");
    });
  });

  it("doesn't render anything when not authenticated", async () => {
    const router = createMemoryRouter(
      [
        {
          element: <RequireLogin />,
          children: [
            {
              path: "/machines",
              element: <>Machines</>,
            },
          ],
        },
      ],
      { initialEntries: ["/machines"] }
    );

    render(
      <Provider store={mockStore(state)}>
        <QueryClientProvider client={queryClient}>
          <WebSocketProvider>
            <RouterProvider router={router} />
          </WebSocketProvider>
        </QueryClientProvider>
      </Provider>
    );

    await waitFor(() => {
      expect(screen.queryByText("Machines")).not.toBeInTheDocument();
    });
  });

  it("renders child routes when logged in", async () => {
    state.status.authenticated = true;
    state.config.items = [
      factory.config({ name: ConfigNames.COMPLETED_INTRO, value: true }),
    ];
    renderFn();

    await waitFor(() => {
      expect(screen.getByText("Machines")).toBeInTheDocument();
    });
  });

  it("redirects to the intro page if intro not completed", async () => {
    state.status.authenticated = true;
    state.config.items = [
      factory.config({ name: ConfigNames.COMPLETED_INTRO, value: false }),
    ];
    const { router } = renderFn();

    await waitFor(() => {
      expect(authResolvers.getCurrentUser.resolved).toBe(true);
    });
    await waitFor(() => {
      expect(router.state.location.pathname).toBe(urls.intro.index);
    });
  });

  it("redirects to the user intro page if user intro not completed", async () => {
    const userId = 1;
    state.status.authenticated = true;
    state.config.items = [
      factory.config({ name: ConfigNames.COMPLETED_INTRO, value: true }),
    ];
    mockServer.use(
      authResolvers.getCurrentUser.handler(factory.user({ id: userId })),
      authResolvers.getMeStatistics.handler(
        factory.userStatistics({ id: userId, completed_intro: false })
      )
    );

    const { router } = renderFn();

    await waitFor(() => {
      expect(authResolvers.getCurrentUser.resolved).toBe(true);
    });
    await waitFor(() => {
      expect(router.state.location.pathname).toBe(urls.intro.user);
    });
  });
});
