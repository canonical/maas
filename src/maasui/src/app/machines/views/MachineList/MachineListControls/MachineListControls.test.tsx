import MachineListControls from "./MachineListControls";

import { machineActions } from "@/app/store/machine";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

describe("MachineListControls", () => {
  let initialState: RootState;

  beforeEach(() => {
    initialState = factory.rootState();
    initialState.machine = factory.machineState({
      loaded: true,
      loading: false,
      filtersLoaded: true,
      filtersLoading: false,
      items: [
        factory.machine({
          fqdn: "abc123",
          system_id: "abc123",
          is_dpu: false,
        }),
      ],
    });
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("changes the filter when the filter accordion changes", async () => {
    const setFilter = vi.fn();
    renderWithProviders(
      <MachineListControls
        filter=""
        grouping={null}
        hiddenColumns={[]}
        machineCount={1}
        resourcePoolsCount={1}
        setFilter={setFilter}
        setGrouping={vi.fn()}
        setHiddenColumns={vi.fn()}
        setHiddenGroups={vi.fn()}
      />,
      { initialEntries: ["/machines?q=test+search"], state: initialState }
    );
    await userEvent.clear(screen.getByRole("searchbox", { name: "Search" }));
    await userEvent.type(
      screen.getByRole("searchbox", { name: "Search" }),
      "status:new"
    );
    await waitFor(() => {
      expect(setFilter).toHaveBeenCalledWith("status:new");
    });
  });

  it("shows search bar, filter accordion, and grouping select when no machines are selected", () => {
    renderWithProviders(
      <MachineListControls
        filter=""
        grouping={null}
        hiddenColumns={[]}
        machineCount={1}
        resourcePoolsCount={1}
        setFilter={vi.fn()}
        setGrouping={vi.fn()}
        setHiddenColumns={vi.fn()}
        setHiddenGroups={vi.fn()}
      />,
      { state: initialState }
    );

    expect(screen.getByRole("button", { name: "Filters" })).toBeInTheDocument();
    expect(
      screen.getByRole("searchbox", { name: "Search" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Group by" })
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("button", { name: "Actions" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Power" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Troubleshoot" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Categorise" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Lock" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Delete" })
    ).not.toBeInTheDocument();
  });

  it("hides search bar, filter accordion, and grouping select when machines are selected", () => {
    initialState.machine.selected = { items: ["abc123"] };
    renderWithProviders(
      <MachineListControls
        filter=""
        grouping={null}
        hiddenColumns={[]}
        machineCount={1}
        resourcePoolsCount={1}
        setFilter={vi.fn()}
        setGrouping={vi.fn()}
        setHiddenColumns={vi.fn()}
        setHiddenGroups={vi.fn()}
      />,
      { state: initialState }
    );

    expect(screen.getByRole("button", { name: "Actions" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Power" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Troubleshoot" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Categorise" })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Lock" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();

    expect(
      screen.queryByRole("button", { name: "Filters" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("searchbox", { name: "Search" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "Group by" })
    ).not.toBeInTheDocument();
  });

  it("dispatches an action to clear selected machines when the 'Clear selection' button is clicked", async () => {
    initialState.machine.selected = { items: ["abc123"] };
    const { store } = renderWithProviders(
      <MachineListControls
        filter=""
        grouping={null}
        hiddenColumns={[]}
        machineCount={1}
        resourcePoolsCount={1}
        setFilter={vi.fn()}
        setGrouping={vi.fn()}
        setHiddenColumns={vi.fn()}
        setHiddenGroups={vi.fn()}
      />,
      { state: initialState }
    );

    const clearSelection = screen.getByRole("button", {
      name: "Clear selection",
    });

    await userEvent.click(clearSelection);

    const actions = store.getActions();
    expect(actions).toEqual(
      expect.arrayContaining([machineActions.setSelected(null)])
    );
  });
});
