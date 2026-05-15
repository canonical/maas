import MachinesFilterOptions, { Label } from "./MachinesFilterOptions";

import { machineActions } from "@/app/store/machine";
import type { FilterGroup } from "@/app/store/machine/types";
import { FilterGroupKey } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

describe("MachinesFilterOptions", () => {
  let state: RootState;
  let filterGroup: FilterGroup;

  beforeEach(() => {
    filterGroup = factory.machineFilterGroup({
      key: FilterGroupKey.Status,
      options: [{ key: "status1", label: "Status 1" }],
      loaded: true,
    });
    state = factory.rootState({
      machine: factory.machineState({
        filters: [filterGroup],
        filtersLoaded: true,
      }),
    });
  });

  it("fetches options if they haven't been loaded", async () => {
    filterGroup.loaded = false;
    filterGroup.loading = false;

    const { store } = renderWithProviders(
      <MachinesFilterOptions
        group={FilterGroupKey.Status}
        setSearchText={vi.fn()}
      />,
      { state }
    );
    const expected = machineActions.filterOptions(FilterGroupKey.Status);
    await waitFor(() => {
      expect(
        store.getActions().find((action) => action.type === expected.type)
      ).toStrictEqual(expected);
    });
  });

  it("does not fetch options if they're loading", async () => {
    filterGroup.loaded = false;
    filterGroup.loading = true;

    const { store } = renderWithProviders(
      <MachinesFilterOptions
        group={FilterGroupKey.Status}
        setSearchText={vi.fn()}
      />,
      { state }
    );
    const expected = machineActions.filterOptions(FilterGroupKey.Status);
    await waitFor(() => {
      expect(
        store.getActions().filter((action) => action.type === expected.type)
      ).toHaveLength(0);
    });
  });

  it("does not fetch options if they have already loaded", async () => {
    filterGroup.loaded = true;
    filterGroup.loading = false;

    const { store } = renderWithProviders(
      <MachinesFilterOptions
        group={FilterGroupKey.Status}
        setSearchText={vi.fn()}
      />,
      { state }
    );
    const expected = machineActions.filterOptions(FilterGroupKey.Status);
    await waitFor(() => {
      expect(
        store.getActions().filter((action) => action.type === expected.type)
      ).toHaveLength(0);
    });
  });

  it("displays a spinner while loading options", async () => {
    filterGroup.loaded = false;
    filterGroup.loading = true;

    renderWithProviders(
      <MachinesFilterOptions
        group={FilterGroupKey.Status}
        setSearchText={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByText(Label.Loading)).toBeInTheDocument();
  });

  it("displays a message if there are no options", async () => {
    filterGroup.options = [];
    renderWithProviders(
      <MachinesFilterOptions
        group={FilterGroupKey.Status}
        setSearchText={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByText(Label.None)).toBeInTheDocument();
  });

  it("displays options", async () => {
    renderWithProviders(
      <MachinesFilterOptions
        group={FilterGroupKey.Status}
        setSearchText={vi.fn()}
      />,
      { state }
    );
    expect(
      screen.getByRole("checkbox", { name: "Status 1" })
    ).toBeInTheDocument();
  });

  it("displays active options", async () => {
    renderWithProviders(
      <MachinesFilterOptions
        group={FilterGroupKey.Status}
        searchText="status:(=status1)"
        setSearchText={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByRole("checkbox", { name: "Status 1" })).toBeChecked();
  });

  it("can set a filter", async () => {
    const setSearchText = vi.fn();
    renderWithProviders(
      <MachinesFilterOptions
        group={FilterGroupKey.Status}
        setSearchText={setSearchText}
      />,
      { state }
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "Status 1" }));
    expect(setSearchText).toHaveBeenCalledWith("status:(=status1)");
  });

  it("can set a boolean filter", async () => {
    filterGroup.options = [{ key: true, label: "Yes" }];
    const setSearchText = vi.fn();
    renderWithProviders(
      <MachinesFilterOptions
        group={FilterGroupKey.Status}
        setSearchText={setSearchText}
      />,
      { state }
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "Yes" }));
    expect(setSearchText).toHaveBeenCalledWith("status:(=true)");
  });

  it("can remove a filter", async () => {
    const setSearchText = vi.fn();
    renderWithProviders(
      <MachinesFilterOptions
        group={FilterGroupKey.Status}
        searchText="status:(=status1)"
        setSearchText={setSearchText}
      />,
      { state }
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "Status 1" }));
    expect(setSearchText).toHaveBeenCalledWith("");
  });

  it("displays workload annotation filters", () => {
    filterGroup = factory.machineFilterGroup({
      key: FilterGroupKey.Workloads,
      loaded: true,
      options: [
        { key: "key1:value1", label: "key1: value1" },
        { key: "key1:value2", label: "key1: value2" },
        { key: "key2:value1", label: "key2: value1" },
      ],
    });
    state.machine.filters = [filterGroup];
    renderWithProviders(
      <MachinesFilterOptions
        group={FilterGroupKey.Workloads}
        setSearchText={vi.fn()}
      />,
      { state }
    );

    // The values don't matter, we just need to display
    // how many of each key there are.
    expect(
      screen.getByRole("checkbox", { name: "key1 (2)" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: "key2 (1)" })
    ).toBeInTheDocument();
  });

  it("sets search text for workload annotation filters", async () => {
    filterGroup = factory.machineFilterGroup({
      key: FilterGroupKey.Workloads,
      loaded: true,
      options: [
        { key: "key1:value1", label: "key1: value1" },
        { key: "key2:value1", label: "key2: value1" },
      ],
    });
    state.machine.filters = [filterGroup];
    const setSearchText = vi.fn();
    renderWithProviders(
      <MachinesFilterOptions
        group={FilterGroupKey.Workloads}
        setSearchText={setSearchText}
      />,
      { state }
    );

    await userEvent.click(screen.getByRole("checkbox", { name: "key1 (1)" }));

    // "workload-" prefix should be added to the key.
    expect(setSearchText).toHaveBeenCalledWith("workload-key1:()");

    await userEvent.click(screen.getByRole("checkbox", { name: "key2 (1)" }));

    // second annotation key should be added to search text
    expect(setSearchText).toHaveBeenCalledWith(
      "workload-key1:() workload-key2:()"
    );
  });
});
