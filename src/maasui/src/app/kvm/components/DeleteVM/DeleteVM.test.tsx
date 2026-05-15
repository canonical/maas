import * as reduxToolkit from "@reduxjs/toolkit";

import DeleteVM from "@/app/kvm/components/DeleteVM/DeleteVM";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
  mockSidePanel,
  waitForLoading,
} from "@/testing/utils";

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

const { mockClose } = await mockSidePanel();

describe("DeleteVM", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState();
  });

  it("calls closeSidePanel on cancel click", async () => {
    renderWithProviders(<DeleteVM />, { state });
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls delete VM on save click", async () => {
    const vms = [
      factory.machine({ system_id: "abc123" }),
      factory.machine({ system_id: "def456" }),
    ];
    state.machine = factory.machineState({
      items: vms,
      selected: { items: vms.map((vm) => vm.system_id) },
    });
    const { store } = renderWithProviders(<DeleteVM />, { state });
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Delete 2 VMs" }));
    const dispatchedActions = store.getActions();
    const deleteAction = dispatchedActions.find(
      (action) => action.type === "machine/delete"
    );
    expect(deleteAction).toBeDefined();
  });

  it("displays error messages when delete VM fails", async () => {
    const mockCallId = "mocked-nanoid";
    vi.mocked(reduxToolkit.nanoid).mockReturnValue(mockCallId);

    const vm = factory.machine({ system_id: "abc123" });
    state = factory.rootState({
      machine: factory.machineState({
        items: [vm],
        selected: { items: [vm.system_id] },
        actions: {
          [mockCallId]: factory.machineActionState({
            status: "error",
            errors: "Uh oh!",
          }),
        },
      }),
    });
    renderWithProviders(<DeleteVM />, { state });
    await waitForLoading();
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
