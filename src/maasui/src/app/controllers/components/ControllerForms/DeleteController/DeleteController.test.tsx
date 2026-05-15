import * as reduxToolkit from "@reduxjs/toolkit";

import DeleteController from "@/app/controllers/components/ControllerForms/DeleteController/DeleteController";
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

describe("DeleteController", () => {
  let state: RootState;

  beforeEach(() => {
    const controllers = [
      factory.controller({ system_id: "abc123" }),
      factory.controller({ system_id: "def456" }),
    ];
    state = factory.rootState({
      controller: factory.controllerState({
        items: controllers,
        statuses: {
          abc123: factory.controllerStatus({
            deleting: false,
          }),
          def456: factory.controllerStatus({
            deleting: false,
          }),
        },
      }),
    });
  });

  it("calls closeSidePanel on cancel click", async () => {
    renderWithProviders(
      <DeleteController
        controllers={state.controller.items}
        isViewingDetails={false}
      />,
      {
        state,
      }
    );
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls delete controller on save click", async () => {
    const { store } = renderWithProviders(
      <DeleteController
        controllers={state.controller.items}
        isViewingDetails={false}
      />,
      { state }
    );
    await waitForLoading();
    await userEvent.click(
      screen.getByRole("button", { name: "Delete 2 controllers" })
    );
    const dispatchedActions = store.getActions();
    const deleteAction = dispatchedActions.find(
      (action) => action.type === "controller/delete"
    );
    expect(deleteAction).toBeDefined();
  });

  it("displays error messages when delete controller fails", async () => {
    const mockCallId = "mocked-nanoid";
    vi.mocked(reduxToolkit.nanoid).mockReturnValue(mockCallId);

    const controllers = [
      factory.controller({ system_id: "abc123" }),
      factory.controller({ system_id: "def456" }),
    ];
    state = factory.rootState({
      controller: factory.controllerState({
        items: controllers,
        statuses: {
          abc123: factory.controllerStatus({
            deleting: false,
          }),
          def456: factory.controllerStatus({
            deleting: false,
          }),
        },
        eventErrors: [
          factory.controllerEventError({
            id: "abc123",
            error: "Uh oh!",
            event: "delete",
          }),
        ],
      }),
    });
    renderWithProviders(
      <DeleteController
        controllers={state.controller.items}
        isViewingDetails={false}
      />,
      { state }
    );
    await waitForLoading();
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
