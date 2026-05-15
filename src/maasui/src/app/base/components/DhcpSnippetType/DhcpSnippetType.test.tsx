import DhcpSnippetType from "./DhcpSnippetType";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

let state: RootState;

beforeEach(() => {
  state = factory.rootState({
    controller: factory.controllerState({
      loaded: true,
    }),
    device: factory.deviceState({
      loaded: true,
    }),
    dhcpsnippet: factory.dhcpSnippetState({
      loaded: true,
      items: [
        factory.dhcpSnippet({ id: 1, name: "class", description: "" }),
        factory.dhcpSnippet({
          id: 2,
          name: "lease",
          subnet: 2,
          description: "",
        }),
        factory.dhcpSnippet({
          id: 3,
          name: "boot",
          node: "xyz",
          description: "",
        }),
      ],
    }),
    machine: factory.machineState({
      loaded: true,
      items: [
        factory.machine({
          system_id: "xyz",
          hostname: "machine1",
          domain: factory.modelRef({ name: "test" }),
        }),
      ],
    }),
    subnet: factory.subnetState({
      loaded: true,
      items: [
        factory.subnet({ id: 1, name: "10.0.0.99" }),
        factory.subnet({ id: 2, name: "test.maas" }),
      ],
    }),
  });
});

it("displays a loading component if loading", () => {
  state.controller.loading = true;
  state.device.loading = true;
  state.dhcpsnippet.loading = true;
  state.machine.loading = true;
  state.subnet.loading = true;

  renderWithProviders(<DhcpSnippetType subnetId={808} />, { state });
  expect(screen.getByText("Loading")).toBeInTheDocument();
});

it("displays a global type", () => {
  renderWithProviders(<DhcpSnippetType nodeId={null} subnetId={null} />, {
    state,
  });
  expect(screen.getByText("Global")).toBeInTheDocument();
});

it("can display a Machine type", () => {
  renderWithProviders(<DhcpSnippetType nodeId="xyz" />, { state });
  expect(screen.getByText("Machine")).toBeInTheDocument();
});
