import type { Mock } from "vitest";

import EventLogs, { Label } from "./EventLogs";

import { Labels as ArrowPaginationLabels } from "@/app/base/components/ArrowPagination";
import { MAIN_CONTENT_SECTION_ID } from "@/app/base/components/MainContentSection";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  within,
  renderWithProviders,
  waitFor,
} from "@/testing/utils";

describe("EventLogs", () => {
  let state: RootState;
  let scrollToSpy: Mock;
  let machine: MachineDetails;

  beforeEach(() => {
    scrollToSpy = vi.fn();
    global.scrollTo = scrollToSpy;
    machine = factory.machineDetails({ id: 1, system_id: "abc123" });
    state = factory.rootState({
      event: factory.eventState({
        items: [
          factory.eventRecord({ node_id: 1 }),
          factory.eventRecord({ node_id: 2 }),
        ],
      }),
      machine: factory.machineState({
        items: [machine],
      }),
    });
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("can display the table", () => {
    renderWithProviders(<EventLogs node={machine} />, {
      state,
    });
    expect(screen.getByLabelText(Label.Title)).toBeInTheDocument();
  });

  it("fetches events up to the preload amount", () => {
    const { store } = renderWithProviders(<EventLogs node={machine} />, {
      state,
      initialEntries: [{ pathname: "/machine/abc123", key: "testKey" }],
    });
    const dispatches = store
      .getActions()
      .filter(({ type }) => type === "event/fetch");
    expect(dispatches.length).toBe(1);
    expect(dispatches[0].payload).toStrictEqual({
      params: {
        limit: 201,
        node_id: 1,
      },
    });
  });

  it("fetches more events when the last page is reached", async () => {
    // Create more than the preload amount of events.
    state.event.items = [];
    for (let i = 0; i < 203; i++) {
      state.event.items.push(
        factory.eventRecord({
          node_id: 1,
          created: factory.timestamp("Tue, 16 Mar. 2021 03:04:00"),
        })
      );
    }

    const { store } = renderWithProviders(<EventLogs node={machine} />, {
      state,
      initialEntries: [{ pathname: "/machine/abc123", key: "testKey" }],
    });
    let dispatches = store
      .getActions()
      .filter(({ type }) => type === "event/fetch");
    expect(dispatches.length).toBe(1);
    // Navigate to the last page:
    for (let i = 0; i < 8; i++) {
      await userEvent.click(
        screen.getByRole("button", { name: ArrowPaginationLabels.GoForward })
      );
    }
    dispatches = store
      .getActions()
      .filter(({ type }) => type === "event/fetch");
    expect(dispatches.length).toBe(2);
    expect(dispatches[1].payload).toStrictEqual({
      params: {
        limit: 201,
        node_id: 1,
        start: state.event.items[202].id,
      },
    });
  });

  it("orders the rows by most recent first", () => {
    state.event.items = [
      factory.eventRecord({
        created: factory.timestamp("Tue, 16 Mar. 2021 03:04:00"),
        node_id: 1,
      }),
      factory.eventRecord({
        created: factory.timestamp("Tue, 17 Mar. 2021 03:04:00"),
        node_id: 1,
      }),
    ];
    renderWithProviders(<EventLogs node={machine} />, {
      state,
    });
    const rows = screen.getAllByRole("row");
    expect(
      within(rows[1]).getByText("Tue, 17 Mar. 2021 03:04:00")
    ).toBeInTheDocument();
    expect(
      within(rows[2]).getByText("Tue, 16 Mar. 2021 03:04:00")
    ).toBeInTheDocument();
  });

  it("can filter the events", async () => {
    state.event.items = [
      factory.eventRecord({
        description: "Failed commissioning",
        node_id: 1,
        type: factory.eventType({ description: undefined }),
      }),
      factory.eventRecord({
        description: "Didn't fail",
        node_id: 1,
        type: factory.eventType({ description: undefined }),
      }),
      factory.eventRecord({
        description: "Failed install",
        node_id: 1,
        type: factory.eventType({ description: undefined }),
      }),
    ];
    renderWithProviders(<EventLogs node={machine} />, {
      state,
    });
    await userEvent.type(screen.getByRole("searchbox"), "failed");
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(
      within(rows[1]).getByText("Failed commissioning")
    ).toBeInTheDocument();
    expect(within(rows[2]).getByText("Failed install")).toBeInTheDocument();
  });

  it("can update the number of events per page", async () => {
    for (let i = 0; i < 203; i++) {
      state.event.items.push(
        factory.eventRecord({
          node_id: 1,
          created: factory.timestamp("Tue, 16 Mar. 2021 03:04:00"),
        })
      );
    }
    renderWithProviders(<EventLogs node={machine} />, {
      state,
    });
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(26);
    await userEvent.selectOptions(screen.getByRole("combobox"), "50");
    expect(screen.getAllByRole("row")).toHaveLength(51);
  });

  it("can restore the events per page from local storage", async () => {
    for (let i = 0; i < 203; i++) {
      state.event.items.push(
        factory.eventRecord({
          node_id: 1,
          created: factory.timestamp("Tue, 16 Mar. 2021 03:04:00"),
        })
      );
    }

    renderWithProviders(<EventLogs node={machine} />, {
      state,
      initialEntries: [{ pathname: "/machine/abc123", key: "testKey" }],
    });
    await userEvent.selectOptions(screen.getByRole("combobox"), "100");

    await waitFor(() => {
      expect(screen.getAllByRole("row")).toHaveLength(101);
    });
  });

  it("does not display the scroll-to-top component if there are less than 50 items", async () => {
    state.event.items = [];
    for (let i = 0; i < 5; i++) {
      state.event.items.push(
        factory.eventRecord({
          node_id: 1,
          created: factory.timestamp("Tue, 16 Mar. 2021 03:04:00"),
        })
      );
    }
    renderWithProviders(<EventLogs node={machine} />, {
      state,
    });
    await userEvent.selectOptions(screen.getByRole("combobox"), "50");
    expect(
      screen.queryByRole("link", { name: Label.BackToTop })
    ).not.toBeInTheDocument();
  });

  it("displays the scroll-to-top component if there are at least 50 items", async () => {
    state.event.items = [];
    for (let i = 0; i < 50; i++) {
      state.event.items.push(
        factory.eventRecord({
          node_id: 1,
          created: factory.timestamp("Tue, 16 Mar. 2021 03:04:00"),
        })
      );
    }
    renderWithProviders(<EventLogs node={machine} />, {
      state,
    });
    await userEvent.selectOptions(screen.getByRole("combobox"), "50");
    expect(
      screen.getByRole("link", { name: Label.BackToTop })
    ).toBeInTheDocument();
  });

  it("scrolls to the top when clicking the scroll-to-top component", async () => {
    state.event.items = [];
    for (let i = 0; i < 50; i++) {
      state.event.items.push(
        factory.eventRecord({
          node_id: 1,
          created: factory.timestamp("Tue, 16 Mar. 2021 03:04:00"),
        })
      );
    }
    renderWithProviders(<EventLogs node={machine} />, {
      state,
    });
    await userEvent.selectOptions(screen.getByRole("combobox"), "50");
    expect(window.location.hash).toBe("");
    await userEvent.click(screen.getByRole("link", { name: Label.BackToTop }));
    expect(window.location.hash).toBe(`#${MAIN_CONTENT_SECTION_ID}`);
  });
});
