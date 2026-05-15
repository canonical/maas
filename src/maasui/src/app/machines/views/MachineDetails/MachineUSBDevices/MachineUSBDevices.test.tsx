import MachineUSBDevices from "./MachineUSBDevices";

import { nodeDeviceActions } from "@/app/store/nodedevice";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

describe("MachineUSBDevices", () => {
  it("fetches the machine's node devices on load", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            system_id: "abc123",
          }),
        ],
      }),
    });
    const { store } = renderWithProviders(<MachineUSBDevices />, {
      initialEntries: ["/machine/abc123/usb-devices"],
      pattern: "/machine/:id/usb-devices",
      state,
    });

    const expectedAction = nodeDeviceActions.getByNodeId("abc123");
    expect(
      store.getActions().find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });
});
