import NetworkNotifications from "./NetworkNotifications";

import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import { NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

const machineRoutePattern = `${urls.machines.machine.index(null)}/*`;

describe("NetworkNotifications", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      general: factory.generalState({
        architectures: factory.architecturesState({
          data: ["amd64"],
          loaded: true,
        }),
        powerTypes: factory.powerTypesState({
          data: [factory.powerType()],
        }),
      }),
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            architecture: "amd64",
            events: [factory.machineEvent()],
            system_id: "abc123",
          }),
        ],
      }),
    });
  });

  it("handles no notifications", () => {
    state.machine.items = [
      factory.machineDetails({
        on_network: true,
        osystem: "ubuntu",
        status: NodeStatus.NEW,
        system_id: "abc123",
      }),
    ];
    renderWithProviders(<NetworkNotifications />, {
      state,
      initialEntries: [urls.machines.machine.network({ id: "abc123" })],
      pattern: machineRoutePattern,
    });
    expect(screen.queryByRole("notification")).not.toBeInTheDocument();
  });

  it("can show a network connection message", () => {
    state.machine.items = [
      factory.machineDetails({
        on_network: false,
        system_id: "abc123",
      }),
    ];
    renderWithProviders(<NetworkNotifications />, {
      state,
      initialEntries: [urls.machines.machine.network({ id: "abc123" })],
      pattern: machineRoutePattern,
    });
    expect(
      screen.getByText(/Machine must be connected to a network./i)
    ).toBeInTheDocument();
  });

  it("can show a permissions message", () => {
    state.machine.items[0].status = NodeStatus.DEPLOYING;
    renderWithProviders(<NetworkNotifications />, {
      state,
      initialEntries: [urls.machines.machine.network({ id: "abc123" })],
      pattern: machineRoutePattern,
    });
    expect(
      screen.getByText(/Interface configuration cannot be modified/i)
    ).toBeInTheDocument();
  });

  it("can display a custom image message", () => {
    state.machine.items[0].osystem = "custom";
    renderWithProviders(<NetworkNotifications />, {
      state,
      initialEntries: [urls.machines.machine.network({ id: "abc123" })],
      pattern: machineRoutePattern,
    });
    expect(
      screen.getByText(/Custom images may require special preparation/i)
    ).toBeInTheDocument();
  });
});
