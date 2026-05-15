import VMsActionBar from "./VMsActionBar";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("VMsActionBar", () => {
  it("executes onAddVMClick on add VM button click", async () => {
    const onAddVMClick = vi.fn();
    const state = factory.rootState();

    renderWithProviders(
      <VMsActionBar
        currentPage={1}
        machinesLoading={false}
        onAddVMClick={onAddVMClick}
        searchFilter=""
        setCurrentPage={vi.fn()}
        setSearchFilter={vi.fn()}
        vmCount={2}
      />,
      { state }
    );

    await userEvent.click(screen.getByRole("button", { name: "Add VM" }));

    expect(onAddVMClick).toHaveBeenCalled();
  });

  it("disables VM actions if none are selected", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        selected: null,
      }),
    });

    renderWithProviders(
      <VMsActionBar
        currentPage={1}
        machinesLoading={false}
        onAddVMClick={vi.fn()}
        searchFilter=""
        setCurrentPage={vi.fn()}
        setSearchFilter={vi.fn()}
        vmCount={2}
      />,
      { state }
    );

    expect(
      screen.getByRole("button", { name: "Take action" })
    ).toBeAriaDisabled();
    expect(
      screen.getByRole("button", { name: "Delete VM" })
    ).toBeAriaDisabled();
  });

  it("enables VM actions if at least one is selected", () => {
    const vms = [factory.machine({ system_id: "abc123" })];
    const state = factory.rootState({
      machine: factory.machineState({
        items: vms,
        selected: { items: ["abc123"] },
      }),
    });

    renderWithProviders(
      <VMsActionBar
        currentPage={1}
        machinesLoading={false}
        onAddVMClick={vi.fn()}
        searchFilter=""
        setCurrentPage={vi.fn()}
        setSearchFilter={vi.fn()}
        vmCount={2}
      />,
      { state }
    );

    expect(
      screen.getByRole("button", { name: "Take action" })
    ).not.toBeAriaDisabled();
    expect(
      screen.getByRole("button", { name: "Delete VM" })
    ).not.toBeAriaDisabled();
  });
});
