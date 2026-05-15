import MachineListHeader from "./MachineListHeader";

import urls from "@/app/base/urls";
import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});
const callId = "mocked-nanoid";

describe("MachineListHeader", () => {
  let state: RootState;

  beforeEach(() => {
    vi.spyOn(query, "generateCallId").mockReturnValue(callId);
    const machines = [
      factory.machine({ system_id: "abc123" }),
      factory.machine({ system_id: "def456" }),
    ];
    state = factory.rootState({
      machine: factory.machineState({
        counts: factory.machineStateCounts({
          [callId]: factory.machineStateCount({
            count: 10,
            loaded: true,
            loading: false,
          }),
        }),
        items: machines,
        statuses: {
          abc123: factory.machineStatus({}),
          def456: factory.machineStatus({}),
        },
      }),
    });
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("displays a machine count if machines have loaded", () => {
    state.machine.counts[callId] = factory.machineStateCount({
      count: 2,
      loaded: true,
    });
    renderWithProviders(
      <MachineListHeader
        grouping={null}
        searchFilter=""
        setGrouping={vi.fn()}
        setHiddenColumns={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSearchFilter={vi.fn()}
      />,
      { state, initialEntries: [urls.machines.index] }
    );
    expect(screen.getByTestId("main-toolbar-heading")).toHaveTextContent(
      "2 machines in 0 pools"
    );
  });

  it("hides the add hardware menu when machines are selected", () => {
    state.machine.selected = { items: ["abc123"] };
    renderWithProviders(
      <MachineListHeader
        grouping={null}
        searchFilter=""
        setGrouping={vi.fn()}
        setHiddenColumns={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSearchFilter={vi.fn()}
      />,
      { state, initialEntries: [urls.machines.index] }
    );
    expect(
      screen.queryByRole("button", { name: "Add hardware" })
    ).not.toBeInTheDocument();
    state.machine.selected.items = [];
    renderWithProviders(
      <MachineListHeader
        grouping={null}
        searchFilter=""
        setGrouping={vi.fn()}
        setHiddenColumns={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSearchFilter={vi.fn()}
      />,
      { state, initialEntries: [urls.machines.index] }
    );
    expect(
      screen.getByRole("button", { name: "Add hardware" })
    ).toBeInTheDocument();
  });
});
