import fs from "fs";
import path from "path";

import type { ProfilerOnRenderCallback, ReactNode } from "react";
import { Profiler } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { RenderOptions, RenderResult } from "@testing-library/react";
import { render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { RequestHandler } from "msw";
import { setupServer } from "msw/node";
import { Provider } from "react-redux";
import type { DataRouter, InitialEntry } from "react-router";
import { createMemoryRouter, RouterProvider } from "react-router";
import type { MockStoreEnhanced } from "redux-mock-store";
import configureStore from "redux-mock-store";
import { vi } from "vitest";

import { client } from "@/app/apiclient/client.gen";
import NewSidePanelContextProvider from "@/app/base/side-panel-context";
import { WebSocketProvider } from "@/app/base/websocket-context";
import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  config as configFactory,
  configState as configStateFactory,
  domainState as domainStateFactory,
  fabric as fabricFactory,
  fabricState as fabricStateFactory,
  generalState as generalStateFactory,
  podDetails as podDetailsFactory,
  podState as podStateFactory,
  podStatus as podStatusFactory,
  powerType as powerTypeFactory,
  powerTypesState as powerTypesStateFactory,
  rootState as rootStateFactory,
  spaceState as spaceStateFactory,
  subnet as subnetFactory,
  subnetState as subnetStateFactory,
  vlan as vlanFactory,
  vlanState as vlanStateFactory,
} from "@/testing/factories";

const getMockStore = (state = factory.rootState()) => {
  const mockStore = configureStore();
  return mockStore(state);
};

// Complete initial test state with all queryData loaded and no errors
export const getTestState = (): RootState => {
  const config = configFactory({
    name: ConfigNames.SESSION_LENGTH,
    value: 1209600, // This is the default session length for MAAS in seconds, equivalent to 14 days
  });
  const fabric = fabricFactory({ name: "pxe-fabric" });
  const nonBootVlan = vlanFactory({ fabric: fabric.id });
  const bootVlan = vlanFactory({ fabric: fabric.id, name: "pxe-vlan" });
  const nonBootSubnet = subnetFactory({ vlan: nonBootVlan.id });
  const bootSubnet = subnetFactory({ name: "pxe-subnet", vlan: bootVlan.id });
  const pod = podDetailsFactory({
    attached_vlans: [nonBootVlan.id, bootVlan.id],
    boot_vlans: [bootVlan.id],
    id: 1,
  });
  return rootStateFactory({
    config: configStateFactory({
      loaded: true,
      items: [config],
    }),
    domain: domainStateFactory({
      loaded: true,
    }),
    fabric: fabricStateFactory({
      items: [fabric],
      loaded: true,
    }),
    general: generalStateFactory({
      powerTypes: powerTypesStateFactory({
        data: [powerTypeFactory()],
        loaded: true,
      }),
    }),
    pod: podStateFactory({
      items: [pod],
      loaded: true,
      statuses: { [pod.id]: podStatusFactory() },
    }),
    space: spaceStateFactory({
      loaded: true,
    }),
    subnet: subnetStateFactory({
      items: [nonBootSubnet, bootSubnet],
      loaded: true,
    }),
    vlan: vlanStateFactory({
      items: [nonBootVlan, bootVlan],
      loaded: true,
    }),
  });
};

export const expectTooltipOnHover = async (
  element: Element | null,
  tooltipText: string | RegExp
) => {
  expect(
    screen.queryByRole("tooltip", { name: tooltipText })
  ).not.toBeInTheDocument();

  if (!element) {
    return {
      message: () => `expected the element to exist`,
      pass: false,
    };
  }

  await userEvent.hover(element);

  if (element.querySelector("i")) {
    await userEvent.hover(element.querySelector("i")!);
  }

  const pass = await vi.waitFor(
    () => screen.getAllByRole("tooltip", { name: tooltipText }).length === 1
  );

  if (pass) {
    return {
      message: () =>
        `expected the element not to have tooltip '${tooltipText}'`,
      pass: true,
    };
  } else {
    return {
      message: () => `expected the element to have tooltip '${tooltipText}'`,
      pass: false,
    };
  }
};

type Hook = Parameters<typeof renderHook>[0];
export const renderHookWithMockStore = (
  hook: Hook,
  options?: { initialState?: RootState }
) => {
  let store = configureStore()(options?.initialState || rootStateFactory());
  const wrapper = ({ children }: { children: ReactNode }) => (
    <WebSocketProvider>
      <Provider store={store}>{children}</Provider>
    </WebSocketProvider>
  );

  const result = renderHook(hook, { wrapper });

  const customRerender = (
    newHook?: Hook,
    { state: newState }: { state?: Partial<RootState> } = {}
  ) => {
    if (newState) {
      store = configureStore()({ ...newState });
    }
    result.rerender(newHook);
  };

  return {
    ...result,
    rerender: customRerender,
    store,
  };
};

export const waitFor = vi.waitFor;
export {
  act,
  cleanup,
  fireEvent,
  getDefaultNormalizer,
  render,
  renderHook,
  screen,
  waitForElementToBeRemoved,
  within,
} from "@testing-library/react";
export { default as userEvent } from "@testing-library/user-event";

/* New utils with easier use */
export const BASE_URL = import.meta.env.VITE_APP_MAAS_URL;

type LogEntry = {
  testName: string;
  time: number;
  scope: string;
  message: string;
};

const logsByFile: Record<string, LogEntry[]> = {};
const testStart = performance.now();
const logFile = path.join(process.cwd(), "test-timings.log");

export function logEvent(
  file: string,
  testName: string,
  scope: string,
  message: string
) {
  if (!process.env.MEASURE_UNIT_PERFORMANCE) return;
  const now = performance.now() - testStart;

  if (!logsByFile[file]) {
    logsByFile[file] = [];
  }

  logsByFile[file].push({ testName, time: now, scope, message });
}

export function flushAllLogs() {
  if (!process.env.MEASURE_UNIT_PERFORMANCE) return;
  const lines: string[] = [];

  for (const [file, entries] of Object.entries(logsByFile)) {
    lines.push(`######## ${file} ########`);

    const groupedByTest: Record<string, LogEntry[]> = {};
    for (const entry of entries) {
      if (!groupedByTest[entry.testName]) {
        groupedByTest[entry.testName] = [];
      }
      groupedByTest[entry.testName].push(entry);
    }

    for (const [testName, testEntries] of Object.entries(groupedByTest)) {
      lines.push(`\n=== ${testName.split(">").at(-1)} ===`);
      for (const e of testEntries) {
        lines.push(`[+${e.time.toFixed(1)}ms] [${e.scope}] ${e.message}`);
      }
    }
  }
  lines.push("\n");

  fs.appendFileSync(logFile, lines.join("\n"), "utf-8");
}

/**
 * A function for setting up the MSW with the base testing url.
 *
 * @param handlers The destructured list of request handlers
 * @return The mock server instance
 */
export const setupMockServer = (...handlers: RequestHandler[]) => {
  client.setConfig({ baseUrl: BASE_URL });

  const mockServer = setupServer(...handlers);

  mockServer.events.on("request:start", ({ request }) => {
    logEvent(
      expect.getState().testPath?.split("/").pop() || "unknown file",
      expect.getState().currentTestName || "unknown",
      "request:start",
      `[msw] → Request: ${request.method} ${request.url}`
    );
  });

  mockServer.events.on("request:end", ({ request }) => {
    logEvent(
      expect.getState().testPath?.split("/").pop() || "unknown file",
      expect.getState().currentTestName || "unknown",
      "request:end",
      `[msw] ← Response: ${request.method} ${request.url}`
    );
  });

  beforeAll(() => {
    mockServer.listen({ onUnhandledRequest: "error" });
  });
  afterEach(() => {
    mockServer.resetHandlers();
  });
  afterAll(() => {
    mockServer.close();
    flushAllLogs();
  });

  return mockServer;
};

/**
 * A function for rendering a component with all test-relevant providers.
 *
 * @param ui The component to be rendered
 * @param options The rendering options
 * @returns { result, router, rerender, store }
 */
export const renderWithProviders = (
  ui: ReactNode,
  options?: Omit<RenderOptions, "wrapper"> &
    Partial<{
      state?: Partial<RootState>;
      store?: MockStoreEnhanced<RootState | unknown>;
      initialEntries?: InitialEntry[];
      pattern?: string;
    }>
): {
  result: RenderResult;
  router: DataRouter;
  rerender: (
    ui: ReactNode,
    {
      state,
    }?: {
      state?: RootState;
    }
  ) => void;
  store: MockStoreEnhanced<RootState | unknown>;
} => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });

  const router = createMemoryRouter(
    [
      {
        path: options?.pattern ?? "*",
        element: ui,
      },
    ],
    { initialEntries: options?.initialEntries || ["/"] }
  );

  let store =
    options?.store ??
    getMockStore({
      ...factory.rootState(),
      ...options?.state,
    });

  const onRender: ProfilerOnRenderCallback = (
    _id,
    phase,
    actualDuration,
    _baseDuration,
    _startTime,
    _commitTime
  ) => {
    logEvent(
      expect.getState().testPath?.split("/").pop() || "unknown file",
      expect.getState().currentTestName || "unknown",
      "render",
      `[${phase}], took ${actualDuration.toFixed(2)}ms`
    );
  };

  const Wrapper = ({ children }: { children: ReactNode }) => {
    return (
      <Profiler id="TestComponent" onRender={onRender}>
        <QueryClientProvider client={queryClient}>
          <WebSocketProvider>
            <NewSidePanelContextProvider>
              <Provider store={store}>{children}</Provider>
            </NewSidePanelContextProvider>
          </WebSocketProvider>
        </QueryClientProvider>
      </Profiler>
    );
  };

  const rendered = render(<RouterProvider router={router} />, {
    wrapper: Wrapper,
    ...options,
  });

  const customRerender = (
    ui: ReactNode,
    { state: newState }: { state?: RootState } = {}
  ) => {
    if (newState) {
      store = getMockStore({ ...options?.state, ...newState });
    }
    const router = createMemoryRouter(
      [
        {
          path: options?.pattern ?? "*",
          element: ui,
        },
      ],
      { initialEntries: options?.initialEntries || ["/"] }
    );

    return rendered.rerender(
      <Wrapper>
        <RouterProvider router={router} />
      </Wrapper>
    );
  };

  return {
    result: rendered,
    rerender: customRerender,
    router,
    store,
  };
};

/**
 * A function for rendering a hook with all test-relevant providers.
 *
 * @param hook The hook to be rendered
 * @param options
 * @returns { rerender, result, unmount, store }
 */
export const renderHookWithProviders = <T,>(
  hook: () => T,
  options?: Partial<{
    state: Partial<RootState>;
    store: MockStoreEnhanced<RootState | unknown>;
    initialEntries: string[];
  }>
): {
  result: { current: T };
  store: MockStoreEnhanced<RootState | unknown>;
  queryClient: QueryClient;
} => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });

  const store =
    options?.store ??
    configureStore()({
      ...factory.rootState(),
      ...options?.state,
    });

  return {
    result: renderHook(hook, {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>
          <WebSocketProvider>
            <NewSidePanelContextProvider>
              <Provider store={store}>{children}</Provider>
            </NewSidePanelContextProvider>
          </WebSocketProvider>
        </QueryClientProvider>
      ),
    }).result,
    store,
    queryClient,
  };
};

/**
 * Mocks the useQuery hook to return a pending state.
 */
export const mockIsPending = () => {
  vi.doMock("@tanstack/react-query", async () => {
    const actual: object = await vi.importActual("@tanstack/react-query");
    return {
      ...actual,
      useQuery: vi.fn().mockReturnValueOnce({
        data: null,
        isPending: true,
        failureReason: undefined,
        isFetched: false,
      }),
    };
  });

  afterEach(() => {
    vi.doUnmock("@tanstack/react-query");
  });
};

/**
 * Waits until the loading text is no longer present in the document.
 *
 * @param loadingText The text to query for. Defaults to "Loading".
 * @param options
 */
export const waitForLoading = async (
  loadingText: string = "Loading",
  options?: { interval?: number; timeout?: number }
) =>
  await waitFor(
    () =>
      expect(
        screen.queryByText(new RegExp(loadingText, "i"))
      ).not.toBeInTheDocument(),
    options
  );

/**
 * Spies on a given mutation hook to observe the mutation function
 * @param obj The module that the hook belongs to
 * @param methodName The name of the mutation hook to spy on
 * @returns A mock function that can be observed
 */
export const spyOnMutation = (obj: unknown, methodName: string) => {
  const mockMutate = vi.fn();
  vi.spyOn(obj, methodName as never).mockImplementation(() => {
    return {
      mutate: mockMutate,
      mutateAsync: vi.fn(),
      data: undefined,
      error: null,
      variables: undefined,
      isError: false,
      isPending: false,
      isIdle: true,
      isSuccess: false,
      status: "idle",
      reset: vi.fn(),
      context: null,
      failureCount: 0,
      failureReason: null,
      isPaused: false,
      submittedAt: 0,
    };
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  return mockMutate;
};

/**
 * Mocks the generic side panel context
 * @returns A mock functions for opening and closing the side panel
 */
export const mockSidePanel = async () => {
  const mockUseSidePanel = vi.spyOn(
    await import("@/app/base/side-panel-context"),
    "useSidePanel"
  );

  const mockOpen = vi.fn();
  const mockClose = vi.fn();

  let isOpen = false;

  beforeEach(() => {
    vi.clearAllMocks();
    isOpen = false;

    mockOpen.mockImplementation(() => {
      isOpen = true;
      mockUseSidePanel.mockReturnValue({
        isOpen: true,
        title: "",
        size: "regular",
        component: null,
        props: {},
        openSidePanel: mockOpen,
        closeSidePanel: mockClose,
        setSidePanelSize: vi.fn(),
      });
    });

    mockClose.mockImplementation(() => {
      isOpen = false;
      mockUseSidePanel.mockReturnValue({
        isOpen: false,
        title: "",
        size: "regular",
        component: null,
        props: {},
        openSidePanel: mockOpen,
        closeSidePanel: mockClose,
        setSidePanelSize: vi.fn(),
      });
    });

    mockUseSidePanel.mockReturnValue({
      isOpen,
      title: "",
      size: "regular",
      component: null,
      props: {},
      openSidePanel: mockOpen,
      closeSidePanel: mockClose,
      setSidePanelSize: vi.fn(),
    });
  });

  return { mockOpen, mockClose };
};
