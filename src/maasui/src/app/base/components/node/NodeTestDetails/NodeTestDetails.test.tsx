import NodeTestDetails from "./NodeTestDetails";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, within } from "@/testing/utils";

const getReturnPath = (id: string) => `/some/url/${id}`;

describe("NodeTestDetails", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machineDetails({
            locked: false,
            permissions: ["edit"],
            system_id: "abc123",
          }),
        ],
      }),
      scriptresult: factory.scriptResultState({
        loaded: true,
        items: [factory.scriptResult()],
      }),
    });
  });

  it("shows the right columns", () => {
    const scriptResult = factory.scriptResult({ id: 1 });
    const scriptResults = [scriptResult];
    state.nodescriptresult.items = { abc123: [1] };
    state.scriptresult.items = scriptResults;
    renderWithProviders(<NodeTestDetails getReturnPath={getReturnPath} />, {
      initialEntries: ["/machine/abc123/testing/1/details"],
      pattern: "/machine/:id/testing/:scriptResultId/details",
      state,
    });
    [
      "Status",
      "Exit Status",
      "Tags",
      "Start time",
      "End time",
      "Runtime",
    ].forEach((column) => {
      expect(
        screen.getByRole("columnheader", {
          name: new RegExp(`^${column}`, "i"),
        })
      ).toBeInTheDocument();
    });
  });

  it("displays a spinner when loading", () => {
    state.scriptresult.loading = true;
    renderWithProviders(<NodeTestDetails getReturnPath={getReturnPath} />, {
      initialEntries: ["/machine/abc123/testing/1/details"],
      pattern: "/machine/:id/testing/:scriptResultId/details",
      state,
    });
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("displays a message if script results aren't found", () => {
    state.scriptresult.items = [];
    renderWithProviders(<NodeTestDetails getReturnPath={getReturnPath} />, {
      initialEntries: ["/machine/abc123/testing/1/details"],
      pattern: "/machine/:id/testing/:scriptResultId/details",
      state,
    });
    expect(screen.getByTestId("not-found")).toBeInTheDocument();
  });

  it("fetches script results", () => {
    const scriptResult = factory.scriptResult({ id: 1 });
    const scriptResults = [scriptResult];
    state.nodescriptresult.items = { abc123: [1] };
    state.scriptresult.items = scriptResults;

    const { store } = renderWithProviders(
      <NodeTestDetails getReturnPath={getReturnPath} />,
      {
        initialEntries: ["/machine/abc123/testing/1/details"],
        pattern: "/machine/:id/testing/:scriptResultId/details",
        state,
      }
    );

    expect(
      store.getActions().find((action) => action.type === "scriptresult/get")
    ).toStrictEqual({
      meta: {
        method: "get",
        model: "noderesult",
      },
      payload: {
        params: {
          id: 1,
        },
      },
      type: "scriptresult/get",
    });
  });

  it("only fetches script results once", () => {
    const scriptResult = factory.scriptResult({ id: 1 });
    const scriptResults = [scriptResult];
    state.nodescriptresult.items = { abc123: [1] };
    state.scriptresult.items = scriptResults;
    const { rerender, store } = renderWithProviders(
      <NodeTestDetails getReturnPath={getReturnPath} />,
      {
        initialEntries: ["/machine/abc123/testing/1/details"],
        pattern: "/machine/:id/testing/:scriptResultId/details",
        state,
      }
    );
    expect(
      store.getActions().filter((action) => action.type === "scriptresult/get")
        .length
    ).toBe(1);
    rerender(<NodeTestDetails getReturnPath={getReturnPath} />, { state });
    expect(
      store.getActions().filter((action) => action.type === "scriptresult/get")
        .length
    ).toBe(1);
  });

  it("displays script result details", () => {
    const scriptResult = factory.scriptResult({ id: 1 });
    const scriptResults = [scriptResult];
    state.nodescriptresult.items = { abc123: [1] };
    state.scriptresult.items = scriptResults;

    renderWithProviders(<NodeTestDetails getReturnPath={getReturnPath} />, {
      initialEntries: ["/machine/abc123/testing/1/details"],
      pattern: "/machine/:id/testing/:scriptResultId/details",
      state,
    });

    expect(screen.getByText(scriptResult.status_name)).toBeInTheDocument();
    expect(screen.getByText(scriptResult.status_name).firstChild).toHaveClass(
      "p-icon--success"
    );
  });

  it("displays script result metrics", () => {
    const metrics = factory.scriptResultResult({
      title: "test-title",
      value: "test-value",
    });
    const scriptResults = [factory.scriptResult({ id: 1, results: [metrics] })];

    state.nodescriptresult.items = { abc123: [1] };
    state.scriptresult.items = scriptResults;

    renderWithProviders(<NodeTestDetails getReturnPath={getReturnPath} />, {
      initialEntries: ["/machine/abc123/testing/1/details"],
      pattern: "/machine/:id/testing/:scriptResultId/details",
      state,
    });

    const metricsTable = screen.getByTestId("script-details-metrics");
    expect(metricsTable).toBeInTheDocument();
    expect(
      within(within(metricsTable).getAllByRole("row")[0]).getAllByRole(
        "gridcell"
      )[0]
    ).toHaveTextContent("test-title");
    expect(
      within(within(metricsTable).getAllByRole("row")[0]).getAllByRole(
        "gridcell"
      )[1]
    ).toHaveTextContent("test-value");
  });

  it("fetches script result logs", () => {
    const scriptResults = [factory.scriptResult({ id: 1 })];

    state.nodescriptresult.items = { abc123: [1] };
    state.scriptresult.items = scriptResults;

    const { store } = renderWithProviders(
      <NodeTestDetails getReturnPath={getReturnPath} />,
      {
        initialEntries: ["/machine/abc123/testing/1/details"],
        pattern: "/machine/:id/testing/:scriptResultId/details",
        state,
      }
    );
    const actions = store
      .getActions()
      .filter((action) => action.type === "scriptresult/getLogs");
    expect(actions[0].payload.params.data_type).toEqual("combined");
    expect(actions[1].payload.params.data_type).toEqual("stdout");
    expect(actions[2].payload.params.data_type).toEqual("stderr");
    expect(actions[3].payload.params.data_type).toEqual("result");
  });

  it("renders a return link", () => {
    const scriptResult = factory.scriptResult({ id: 1 });
    state.scriptresult.items = [scriptResult];
    state.nodescriptresult.items = { abc123: [scriptResult.id] };

    renderWithProviders(<NodeTestDetails getReturnPath={getReturnPath} />, {
      initialEntries: ["/machine/abc123/testing/1/details"],
      pattern: "/machine/:id/testing/:scriptResultId/details",
      state,
    });

    expect(
      screen.getByRole("link", { name: "‹ Back to test results" })
    ).toHaveAttribute("href", getReturnPath("abc123"));
  });
});
