import MachineSelectTable, { Label } from "./MachineSelectTable";

import type { Machine } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  within,
  renderWithProviders,
} from "@/testing/utils";

describe("MachineSelectTable", () => {
  let machines: Machine[];
  let state: RootState;

  beforeEach(() => {
    machines = [
      factory.machine({
        system_id: "abc123",
        hostname: "first",
        owner: "admin",
        tags: [12],
      }),
      factory.machine({
        system_id: "def456",
        hostname: "second",
        owner: "user",
        tags: [13],
      }),
    ];
    state = factory.rootState({
      machine: factory.machineState({
        items: machines,
      }),
      tag: factory.tagState({
        items: [
          factory.tag({ id: 12, name: "tagA" }),
          factory.tag({ id: 13, name: "tagB" }),
        ],
      }),
    });
  });

  it("shows a loading skeleton while data is loading", () => {
    state.machine.loading = true;
    renderWithProviders(
      <MachineSelectTable
        machines={machines}
        onMachineClick={vi.fn()}
        pageSize={machines.length}
        searchText=""
        setSearchText={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByRole("grid")).toHaveAttribute("aria-busy", "true");
  });

  it("highlights the substring that matches the search text", async () => {
    renderWithProviders(
      <MachineSelectTable
        machines={[machines[0]]}
        onMachineClick={vi.fn()}
        pageSize={machines.length}
        searchText="fir"
        setSearchText={vi.fn()}
      />,
      { state }
    );

    const hostnameCol = screen.getByRole("gridcell", {
      name: Label.Hostname,
    });

    expect(hostnameCol.querySelector("strong")).toHaveTextContent("fir");
  });

  it("runs onMachineClick function on row click", async () => {
    const onMachineClick = vi.fn();

    renderWithProviders(
      <MachineSelectTable
        machines={machines}
        onMachineClick={onMachineClick}
        pageSize={machines.length}
        searchText=""
        setSearchText={vi.fn()}
      />,
      { state }
    );

    await userEvent.click(screen.getByRole("row", { name: "first" }));
    expect(onMachineClick).toHaveBeenCalledWith(machines[0]);
  });

  it("displays tag names", () => {
    renderWithProviders(
      <MachineSelectTable
        machines={machines}
        onMachineClick={vi.fn()}
        pageSize={machines.length}
        searchText=""
        setSearchText={vi.fn()}
      />,
      { state }
    );
    const ownerCols = screen.getAllByRole("gridcell", {
      name: Label.Owner,
    });
    expect(within(ownerCols[0]).getByText("tagA")).toBeInTheDocument();
  });

  it("can select machine by pressing Enter key", async () => {
    const onMachineClick = vi.fn();
    const machine = machines[0];
    renderWithProviders(
      <MachineSelectTable
        machines={machines}
        onMachineClick={onMachineClick}
        pageSize={machines.length}
        searchText=""
        setSearchText={vi.fn()}
      />,
      { state }
    );
    screen
      .getByRole("row", {
        name: machine.hostname,
      })
      .focus();
    await userEvent.keyboard("{enter}");
    expect(onMachineClick).toHaveBeenCalledWith(machine);
  });

  it("renders with partial search string", async () => {
    const onMachineClick = vi.fn();
    renderWithProviders(
      <MachineSelectTable
        machines={machines}
        onMachineClick={onMachineClick}
        pageSize={machines.length}
        searchText="id:("
        setSearchText={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByRole("grid")).toBeInTheDocument();
  });
});
