import SetMachineZoneForm from "./SetMachineZoneForm";

import * as query from "@/app/store/machine/utils/query";
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

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

describe("SetMachineZoneForm", () => {
  let state: RootState;
  const machines = [
    factory.machine({ system_id: "abc123" }),
    factory.machine({ system_id: "def456" }),
  ];

  beforeEach(() => {
    vi.spyOn(query, "generateCallId").mockReturnValue("123456");
    state = factory.rootState({
      machine: factory.machineState({
        errors: {},
        loading: false,
        loaded: true,
        items: machines,
        selected: {
          items: machines.map((machine) => machine.system_id),
        },
        statuses: {
          abc123: factory.machineStatus({
            settingZone: false,
          }),
          def456: factory.machineStatus({
            settingZone: false,
          }),
        },
      }),
    });
  });

  it("renders the form with the correct count on the submit label", () => {
    renderWithProviders(<SetMachineZoneForm isViewingDetails={false} />, {
      state,
    });

    expect(screen.getByRole("combobox", { name: "Zone" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Set zone for 2 machines" })
    ).toBeInTheDocument();
  });

  it("dispatches actions to update machine zones", async () => {
    const { store } = renderWithProviders(
      <SetMachineZoneForm isViewingDetails={false} />,
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
        payload: undefined,
        type: "machine/cleanup",
      },
      {
        meta: {
          method: "action",
          model: "machine",
        },
        payload: {
          params: {
            action: NodeActions.SET_ZONE,
            extra: {
              zone_id: "1",
            },
            filter: {
              id: machines.map((machine) => machine.system_id),
            },
            system_id: undefined,
          },
        },
        type: "machine/setZone",
      },
    ];

    expect(store.getActions()).toEqual(expectedActions);
  });
});
