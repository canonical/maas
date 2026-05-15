import MarkConnectedForm, { ConnectionState } from "./MarkConnectedForm";

import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

let state: RootState;

beforeEach(() => {
  state = factory.rootState({
    machine: factory.machineState({
      items: [
        factory.machineDetails({
          system_id: "abc123",
        }),
      ],
      statuses: factory.machineStatuses({
        abc123: factory.machineStatus(),
      }),
    }),
  });
});

it("renders a mark connected form", () => {
  const nic = factory.machineInterface({
    type: NetworkInterfaceTypes.PHYSICAL,
    link_connected: false,
  });
  state.machine.items = [
    factory.machineDetails({
      system_id: "abc123",
      interfaces: [nic],
    }),
  ];
  renderWithProviders(
    <MarkConnectedForm
      connectionState={ConnectionState.MARK_CONNECTED}
      nic={nic}
      systemId="abc123"
    />,
    { state }
  );

  expect(
    screen.getByRole("form", { name: "Mark connected" })
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Mark as connected" })
  ).toBeInTheDocument();
});

it("renders a mark disconnected form", () => {
  const nic = factory.machineInterface({
    type: NetworkInterfaceTypes.PHYSICAL,
    link_connected: true,
  });
  state.machine.items = [
    factory.machineDetails({
      system_id: "abc123",
      interfaces: [nic],
    }),
  ];
  renderWithProviders(
    <MarkConnectedForm
      connectionState={ConnectionState.MARK_DISCONNECTED}
      nic={nic}
      systemId="abc123"
    />,
    { state }
  );

  expect(
    screen.getByRole("form", { name: "Mark disconnected" })
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Mark as disconnected" })
  ).toBeInTheDocument();
});

it("displays a disconnected warning", () => {
  const nic = factory.machineInterface({
    type: NetworkInterfaceTypes.PHYSICAL,
    link_connected: false,
  });
  state.machine.items = [
    factory.machineDetails({
      system_id: "abc123",
      interfaces: [nic],
    }),
  ];
  renderWithProviders(
    <MarkConnectedForm
      connectionState={ConnectionState.DISCONNECTED_WARNING}
      nic={nic}
      systemId="abc123"
    />,
    { state }
  );

  expect(
    screen.getByRole("form", { name: "Mark connected" })
  ).toBeInTheDocument();
  expect(
    screen.getByText(/If this is no longer true, mark cable as connected/i) // using this phrase because the warning is broken into different lines
  ).toBeInTheDocument();
});
