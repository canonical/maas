import DeviceActionFormWrapper from "./DeviceActionFormWrapper";

import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("DeviceActionFormWrapper", () => {
  it("can set selected devices to those that can perform action", async () => {
    const state = factory.rootState();
    const devices = [
      factory.device({ system_id: "abc123", actions: [NodeActions.DELETE] }),
      factory.device({ system_id: "def456", actions: [] }),
    ];

    const setRowSelection = vi.fn();
    renderWithProviders(
      <DeviceActionFormWrapper
        action={NodeActions.DELETE}
        devices={devices}
        setRowSelection={setRowSelection}
        viewingDetails={false}
      />,
      { state }
    );

    await userEvent.click(screen.getByTestId("on-update-selected"));

    expect(setRowSelection).toHaveBeenCalledWith({
      [devices[0].id]: true,
    });
  });
});
