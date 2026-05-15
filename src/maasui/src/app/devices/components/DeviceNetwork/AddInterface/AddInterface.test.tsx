import AddInterface from "./AddInterface";

import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import { DeviceIpAssignment } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

const createNewInterface = async () => {
  await userEvent.clear(screen.getByRole("textbox", { name: "Name" }));
  await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "eth123");

  await userEvent.type(
    screen.getByRole("textbox", { name: "MAC address" }),
    "11:22:33:44:55:66"
  );

  await userEvent.type(screen.getByRole("textbox", { name: "Tags" }), "tag1");

  await userEvent.click(screen.getByTestId("new-tag"));

  await userEvent.type(screen.getByRole("textbox", { name: "Tags" }), "tag2");

  await userEvent.click(screen.getByTestId("new-tag"));

  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "IP assignment" }),
    DeviceIpAssignment.STATIC
  );

  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Subnet" }),
    "2"
  );

  await userEvent.type(
    screen.getByRole("textbox", { name: "IP address" }),
    "192.168.1.1"
  );

  await userEvent.click(screen.getByRole("button", { name: "Save interface" }));
};

describe("AddInterface", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      device: factory.deviceState({
        items: [
          factory.deviceDetails({
            system_id: "abc123",
          }),
        ],
        loaded: true,
        statuses: factory.deviceStatuses({
          abc123: factory.deviceStatus(),
        }),
      }),
      subnet: factory.subnetState({
        items: [factory.subnet({ id: 1 }), factory.subnet({ id: 2 })],
        loaded: true,
      }),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("displays a spinner if device is not detailed version", () => {
    state.device.items[0] = factory.device({ system_id: "abc123" });

    renderWithProviders(<AddInterface systemId="abc123" />, { state });

    expect(screen.getByTestId("loading-device-details"));
  });

  it("correctly dispatches action to create an interface", async () => {
    const { store } = renderWithProviders(<AddInterface systemId="abc123" />, {
      state,
    });

    await createNewInterface();

    const expectedAction = deviceActions.createInterface({
      ip_address: "192.168.1.1",
      ip_assignment: DeviceIpAssignment.STATIC,
      mac_address: "11:22:33:44:55:66",
      name: "eth123",
      subnet: "2",
      tags: ["tag1", "tag2"],
      system_id: "abc123",
    });
    const actualAction = store
      .getActions()
      .find((action) => action.type === expectedAction.type);
    expect(actualAction).toStrictEqual(expectedAction);
  });

  it("does not close the form if there is an error when creating the interface", async () => {
    const closeForm = vi.fn();
    state.device.errors = null;

    const { store } = renderWithProviders(<AddInterface systemId="abc123" />, {
      state,
    });
    await createNewInterface();
    const errors = vi.spyOn(deviceSelectors, "eventErrorsForDevices");
    errors.mockReturnValue([
      factory.deviceEventError({
        event: "createInterface",
      }),
    ]);
    const creatingInterface = vi.spyOn(deviceSelectors, "getStatusForDevice");
    creatingInterface.mockReturnValue(true);
    store.dispatch({ type: "" });
    creatingInterface.mockReturnValue(false);
    store.dispatch({ type: "" });
    expect(closeForm).not.toHaveBeenCalled();
  });

  it("does not close the form if there is an error when submitting the form multiple times", async () => {
    const closeForm = vi.fn();
    state.device.errors = null;

    const { store } = renderWithProviders(<AddInterface systemId="abc123" />, {
      state,
    });
    await createNewInterface();
    const errors = vi.spyOn(deviceSelectors, "eventErrorsForDevices");
    errors.mockReturnValue([
      factory.deviceEventError({
        event: "createInterface",
      }),
    ]);
    const creatingInterface = vi.spyOn(deviceSelectors, "getStatusForDevice");
    creatingInterface.mockReturnValue(true);
    store.dispatch({ type: "" });
    creatingInterface.mockReturnValue(false);
    store.dispatch({ type: "" });
    errors.mockReturnValue([]);
    await userEvent.click(
      screen.getByRole("button", { name: "Save interface" })
    );
    creatingInterface.mockReturnValue(true);
    store.dispatch({ type: "" });
    creatingInterface.mockReturnValue(false);

    // Mock an error for the second submission.
    errors.mockReturnValue([
      factory.deviceEventError({
        event: "createInterface",
      }),
    ]);
    store.dispatch({ type: "" });
    expect(closeForm).not.toHaveBeenCalled();
  });
});
