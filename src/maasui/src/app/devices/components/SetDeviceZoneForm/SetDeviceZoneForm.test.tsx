import SetDeviceZoneForm from "./SetDeviceZoneForm";

import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

setupMockServer(zoneResolvers.listZones.handler());
let state: RootState;

describe("SetZoneForm", () => {
  beforeEach(() => {
    const devices = [
      factory.device({ system_id: "abc123" }),
      factory.device({ system_id: "def456" }),
    ];
    state = factory.rootState({
      device: factory.deviceState({
        items: devices,
        statuses: {
          abc123: factory.deviceStatus({
            settingZone: false,
          }),
          def456: factory.deviceStatus({
            settingZone: false,
          }),
        },
      }),
    });
  });

  it("renders the form with the correct count on the submit label", () => {
    renderWithProviders(
      <SetDeviceZoneForm
        devices={state.device.items}
        isViewingDetails={false}
      />,
      {
        state,
      }
    );

    expect(screen.getByRole("combobox", { name: "Zone" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Set zone for 2 devices" })
    ).toBeInTheDocument();
  });

  it("dispatches actions to update device zones", async () => {
    const { store } = renderWithProviders(
      <SetDeviceZoneForm
        devices={state.device.items}
        isViewingDetails={false}
      />,
      {
        state,
      }
    );

    await waitFor(() => {
      expect(
        screen.getByRole("combobox", { name: "Zone" })
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("combobox", { name: "Zone" }));

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Zone" }),
      "1"
    );
    await userEvent.click(screen.getByRole("button", { name: /Set zone/ }));

    const expectedActions = [
      {
        meta: {
          method: "action",
          model: "device",
        },
        payload: {
          params: {
            action: NodeActions.SET_ZONE,
            extra: {
              zone_id: "1",
            },
            system_id: "abc123",
          },
        },
        type: "device/setZone",
      },
      {
        meta: {
          method: "action",
          model: "device",
        },
        payload: {
          params: {
            action: NodeActions.SET_ZONE,
            extra: {
              zone_id: "1",
            },
            system_id: "def456",
          },
        },
        type: "device/setZone",
      },
    ];

    expect(store.getActions()).toEqual(expectedActions);
  });
});
