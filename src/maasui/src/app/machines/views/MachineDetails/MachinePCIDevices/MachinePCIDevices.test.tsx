import MachinePCIDevices from "./MachinePCIDevices";

import { nodeDeviceActions } from "@/app/store/nodedevice";
import * as factory from "@/testing/factories";
import { renderWithProviders, waitFor } from "@/testing/utils";

describe("MachinePCIDevices", () => {
  it("fetches the machine's node devices on load", async () => {
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            system_id: "abc123",
          }),
        ],
      }),
    });
    const { store } = renderWithProviders(<MachinePCIDevices />, {
      initialEntries: ["/machine/abc123/pci-devices"],
      pattern: "/machine/:id/pci-devices",
      state,
    });

    const expectedAction = nodeDeviceActions.getByNodeId("abc123");
    await waitFor(() => {
      expect(
        store.getActions().find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });
  });
});
