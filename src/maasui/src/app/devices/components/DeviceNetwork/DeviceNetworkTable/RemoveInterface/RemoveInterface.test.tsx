import RemoveInterface from "./RemoveInterface";

import * as analyticsHooks from "@/app/base/hooks/analytics";
import * as baseHooks from "@/app/base/hooks/base";
import { deviceActions } from "@/app/store/device";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("RemoveInterface", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      device: factory.deviceState({
        items: [factory.deviceDetails({ system_id: "abc123" })],
        loaded: true,
        statuses: factory.deviceStatuses({
          abc123: factory.deviceStatus(),
        }),
      }),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends an analytics event and closes the form when saved", () => {
    const useSendMock = vi.spyOn(analyticsHooks, "useSendAnalyticsWhen");
    // Mock interface successfully being deleted.
    vi.spyOn(baseHooks, "useCycled").mockReturnValue([true, () => null]);

    renderWithProviders(<RemoveInterface nicId={1} systemId="abc123" />, {
      state,
    });

    expect(mockClose).toHaveBeenCalled();
    expect(useSendMock.mock.calls[0]).toEqual([
      true,
      "Device network",
      "Remove interface",
      "Remove",
    ]);
  });

  it("can show errors related to deleting the interface", () => {
    state.device.eventErrors = [
      factory.deviceEventError({
        id: "someOtherDevice",
        error: "Some other error for some other device",
        event: "someOtherError",
      }),
      factory.deviceEventError({
        id: "abc123",
        error: "Some other error for this device",
        event: "someOtherError",
      }),
      factory.deviceEventError({
        id: "abc123",
        error: "Delete interface error for this device",
        event: "deleteInterface",
      }),
      factory.deviceEventError({
        id: "someOtherDevice",
        error: "Delete interface error for this device",
        event: "deleteInterface",
      }),
    ];

    renderWithProviders(<RemoveInterface nicId={1} systemId="abc123" />, {
      state,
    });

    expect(
      screen.getByText("Delete interface error for this device")
    ).toBeInTheDocument();
  });

  it("correctly dispatches an action to delete an interface", async () => {
    const { store } = renderWithProviders(
      <RemoveInterface nicId={1} systemId="abc123" />,
      {
        state,
      }
    );

    await userEvent.click(screen.getByRole("button", { name: /remove/i }));

    const expectedAction = deviceActions.deleteInterface({
      interface_id: 1,
      system_id: "abc123",
    });
    const actualAction = store
      .getActions()
      .find((action) => action.type === expectedAction.type);
    expect(actualAction).toStrictEqual(expectedAction);
  });
});
