import EditInterface from "./EditInterface";

import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import type { DeviceNetworkInterface } from "@/app/store/device/types";
import { DeviceIpAssignment } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  mockSidePanel,
  renderWithProviders,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("EditInterface", () => {
  let state: RootState;
  let nic: DeviceNetworkInterface;
  beforeEach(() => {
    nic = factory.deviceInterface();
    state = factory.rootState({
      device: factory.deviceState({
        items: [
          factory.deviceDetails({
            interfaces: [nic],
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

    renderWithProviders(<EditInterface nicId={nic.id} systemId="abc123" />, {
      state,
    });
    expect(screen.getByTestId("loading-device-details")).toBeInTheDocument();
  });

  it("dispatches an action to update an interface", async () => {
    const { store } = renderWithProviders(
      <EditInterface nicId={nic.id} systemId="abc123" />,
      {
        state,
      }
    );
    const formValues = {
      ip_address: "192.168.1.1",
      ip_assignment: DeviceIpAssignment.EXTERNAL,
      mac_address: "11:22:33:44:55:66",
      name: "eth123",
      tags: [],
    };
    await userEvent.clear(screen.getByRole("textbox", { name: "Name" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "Name" }),
      "eth123"
    );

    await userEvent.clear(screen.getByRole("textbox", { name: "MAC address" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "MAC address" }),
      "11:22:33:44:55:66"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "IP assignment" }),
      DeviceIpAssignment.EXTERNAL
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "IP address" }),
      "192.168.1.1"
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Save interface" })
    );

    const expectedAction = deviceActions.updateInterface({
      ...formValues,
      interface_id: nic.id,
      system_id: "abc123",
    });
    const actualAction = store
      .getActions()
      .find((action) => action.type === expectedAction.type);
    expect(actualAction).toStrictEqual(expectedAction);
  });

  it("does not close the form if there is an error when updating the interface", async () => {
    state.device.errors = null;

    const { store } = renderWithProviders(
      <EditInterface nicId={nic.id} systemId={"abc123"} />,
      {
        state,
      }
    );
    await userEvent.clear(screen.getByRole("textbox", { name: "Name" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "Name" }),
      "eth123"
    );
    const errors = vi.spyOn(deviceSelectors, "eventErrorsForDevices");
    errors.mockReturnValue([
      factory.deviceEventError({
        event: "updateInterface",
      }),
    ]);
    const updatingInterface = vi.spyOn(deviceSelectors, "getStatusForDevice");
    updatingInterface.mockReturnValue(true);
    store.dispatch({ type: "" });
    updatingInterface.mockReturnValue(false);
    store.dispatch({ type: "" });
    expect(mockClose).not.toHaveBeenCalled();
  });

  it("does not close the form if there is an error when submitting the form multiple times", async () => {
    state.device.errors = null;

    const { store } = renderWithProviders(
      <EditInterface nicId={nic.id} systemId={"abc123"} />,
      {
        state,
      }
    );
    await userEvent.clear(screen.getByRole("textbox", { name: "Name" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "Name" }),
      "eth123"
    );
    const errors = vi.spyOn(deviceSelectors, "eventErrorsForDevices");
    errors.mockReturnValue([
      factory.deviceEventError({
        event: "updateInterface",
      }),
    ]);
    const updatingInterface = vi.spyOn(deviceSelectors, "getStatusForDevice");
    updatingInterface.mockReturnValue(true);
    store.dispatch({ type: "" });
    updatingInterface.mockReturnValue(false);
    store.dispatch({ type: "" });
    errors.mockReturnValue([]);

    await userEvent.clear(screen.getByRole("textbox", { name: "Name" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "Name" }),
      "eth123"
    );
    updatingInterface.mockReturnValue(true);
    store.dispatch({ type: "" });
    updatingInterface.mockReturnValue(false);
    // Mock an error for the second submission.
    errors.mockReturnValue([
      factory.deviceEventError({
        event: "updateInterface",
      }),
    ]);
    store.dispatch({ type: "" });
    expect(mockClose).not.toHaveBeenCalled();
  });
});
