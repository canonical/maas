import * as reduxToolkit from "@reduxjs/toolkit";

import urls from "@/app/base/urls";
import DeleteMachine from "@/app/machines/components/MachineForms/DeleteMachine/DeleteMachine";
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

describe("DeleteMachine", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState();
  });

  it("calls closeSidePanel on cancel click", async () => {
    renderWithProviders(<DeleteMachine isViewingDetails={false} />, { state });
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls delete machine on save click", async () => {
    const machines = [
      factory.machine({ system_id: "abc123" }),
      factory.machine({ system_id: "def456" }),
    ];
    state.machine = factory.machineState({
      items: machines,
      selected: { items: machines.map((machine) => machine.system_id) },
    });
    const { store } = renderWithProviders(
      <DeleteMachine isViewingDetails={false} />,
      { state }
    );
    await waitForLoading();
    await userEvent.click(
      screen.getByRole("button", { name: "Delete 2 machines" })
    );
    const dispatchedActions = store.getActions();
    const deleteAction = dispatchedActions.find(
      (action) => action.type === "machine/delete"
    );
    expect(deleteAction).toBeDefined();
  });

  it("redirects to machines list if machine deleted from details", async () => {
    const mockCallId = "mocked-nanoid";
    vi.mocked(reduxToolkit.nanoid).mockReturnValue(mockCallId);

    const machine = factory.machine({ system_id: "abc123" });
    state.machine = factory.machineState({
      items: [machine],
      selected: { items: [machine.system_id] },
      actions: {
        [mockCallId]: factory.machineActionState({
          status: "success",
        }),
      },
    });
    const { router } = renderWithProviders(
      <DeleteMachine isViewingDetails={true} />,
      {
        state,
        initialEntries: [
          urls.machines.machine.commissioning.index({ id: machine.system_id }),
        ],
      }
    );
    await waitForLoading();
    await waitFor(() => {
      expect(router.state.location.pathname).toEqual(urls.machines.index);
    });
  });

  it("displays error messages when delete machine fails", async () => {
    const mockCallId = "mocked-nanoid";
    vi.mocked(reduxToolkit.nanoid).mockReturnValue(mockCallId);

    const machine = factory.machine({ system_id: "abc123" });
    state = factory.rootState({
      machine: factory.machineState({
        items: [machine],
        selected: { items: [machine.system_id] },
        actions: {
          [mockCallId]: factory.machineActionState({
            status: "error",
            errors: "Uh oh!",
          }),
        },
      }),
    });
    renderWithProviders(<DeleteMachine isViewingDetails={false} />, { state });
    await waitForLoading();
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
