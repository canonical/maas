import * as reduxToolkit from "@reduxjs/toolkit";

import DeleteDevice from "@/app/devices/components/DeleteDevice/DeleteDevice";
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

describe("DeleteDevice", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      device: factory.deviceState({ items: [factory.device()] }),
    });
  });

  it("calls closeSidePanel on cancel click", async () => {
    renderWithProviders(
      <DeleteDevice devices={state.device.items} isViewingDetails={false} />,
      {
        state,
      }
    );
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls delete device on save click", async () => {
    const { store } = renderWithProviders(
      <DeleteDevice devices={state.device.items} isViewingDetails={false} />,
      { state }
    );
    await waitForLoading();
    await userEvent.click(
      screen.getByRole("button", { name: "Delete device" })
    );
    const dispatchedActions = store.getActions();
    const deleteAction = dispatchedActions.find(
      (action) => action.type === "device/delete"
    );
    expect(deleteAction).toBeDefined();
  });

  it("displays error messages when delete device fails", async () => {
    const mockCallId = "mocked-nanoid";
    vi.mocked(reduxToolkit.nanoid).mockReturnValue(mockCallId);

    state = factory.rootState({
      device: factory.deviceState({
        items: [factory.device({ system_id: "abc123" })],
        eventErrors: [
          factory.deviceEventError({
            id: "abc123",
            error: "Uh oh!",
            event: "delete",
          }),
        ],
      }),
    });
    renderWithProviders(
      <DeleteDevice devices={state.device.items} isViewingDetails={false} />,
      { state }
    );
    await waitForLoading();
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
