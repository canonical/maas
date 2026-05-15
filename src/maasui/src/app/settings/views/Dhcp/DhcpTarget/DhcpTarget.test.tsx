import DhcpTarget from "./DhcpTarget";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("DhcpTarget", () => {
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
    renderWithProviders(<DhcpTarget subnetId={808} />, { state });
    expect(screen.getByText("Loading")).toBeInTheDocument();
  });

  it("can display a subnet link", () => {
    renderWithProviders(<DhcpTarget subnetId={1} />, { state });
    const link = screen.getByRole("link", { name: "10.0.0.99" });

    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/subnet/1");
  });

  it("can display a node link", () => {
    renderWithProviders(<DhcpTarget nodeId="xyz" />, { state });
    const link = screen.getByRole("link", { name: "machine1 .test" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/machine/xyz");
  });
});
