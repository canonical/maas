import SetControllerZoneForm from "./SetControllerZoneForm";

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
    const controllers = [
      factory.controller({ system_id: "abc123" }),
      factory.controller({ system_id: "def456" }),
    ];
    state = factory.rootState({
      controller: factory.controllerState({
        items: controllers,
        statuses: {
          abc123: factory.controllerStatus({
            settingZone: false,
          }),
          def456: factory.controllerStatus({
            settingZone: false,
          }),
        },
      }),
    });
  });

  it("renders the form with the correct count on the submit label", () => {
    renderWithProviders(
      <SetControllerZoneForm
        controllers={state.controller.items}
        isViewingDetails={false}
      />,
      {
        state,
      }
    );

    expect(screen.getByRole("combobox", { name: "Zone" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Set zone for 2 controllers" })
    ).toBeInTheDocument();
  });

  it("dispatches actions to update controller zones", async () => {
    const { store } = renderWithProviders(
      <SetControllerZoneForm
        controllers={state.controller.items}
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
          model: "controller",
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
        type: "controller/setZone",
      },
      {
        meta: {
          method: "action",
          model: "controller",
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
        type: "controller/setZone",
      },
    ];

    expect(store.getActions()).toEqual(expectedActions);
  });
});
