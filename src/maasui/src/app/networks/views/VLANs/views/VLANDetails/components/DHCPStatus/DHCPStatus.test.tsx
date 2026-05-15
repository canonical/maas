import DHCPStatus from "./DHCPStatus";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, within } from "@/testing/utils";

describe("DHCPStatus", () => {
  it("shows a spinner if data is loading", () => {
    const state = factory.rootState({
      subnet: factory.subnetState({ items: [], loading: true }),
      vlan: factory.vlanState({ items: [] }),
    });
    renderWithProviders(<DHCPStatus id={1} />, { state });

    expect(screen.getByTestId("loading-data")).toBeInTheDocument();
  });

  it(`shows a warning and disables Configure DHCP button if there are no subnets
    attached to the VLAN`, () => {
    const vlan = factory.vlan();
    const state = factory.rootState({
      subnet: factory.subnetState({ items: [] }),
      vlan: factory.vlanState({ items: [vlan] }),
    });
    renderWithProviders(<DHCPStatus id={vlan.id} />, { state });
    const dhcpStatus = screen.getByRole("region", { name: "DHCP" });

    expect(
      within(dhcpStatus).getByRole("button", { name: "Configure DHCP" })
    ).toBeAriaDisabled();
    expect(
      within(dhcpStatus).getByText(
        "No subnets are available on this VLAN. DHCP cannot be enabled."
      )
    ).toBeInTheDocument();
  });

  it("does not show a warning if there are subnets attached to the VLAN", () => {
    const subnetId = 1;
    const vlan = factory.vlan({ subnet_ids: [subnetId] });
    const subnet = factory.subnet({ id: subnetId, vlan: vlan.id });
    const state = factory.rootState({
      subnet: factory.subnetState({ items: [subnet] }),
      vlan: factory.vlanState({ items: [vlan] }),
    });
    renderWithProviders(<DHCPStatus id={vlan.id} />, { state });
    const dhcpStatus = screen.getByRole("region", { name: "DHCP" });

    expect(
      within(dhcpStatus).queryByText(
        "No subnets are available on this VLAN. DHCP cannot be enabled."
      )
    ).not.toBeInTheDocument();
  });

  it("renders correctly when a VLAN does not have DHCP enabled", () => {
    const vlan = factory.vlan({
      dhcp_on: false,
      external_dhcp: null,
      relay_vlan: null,
    });
    const state = factory.rootState({
      vlan: factory.vlanState({ items: [vlan] }),
    });
    renderWithProviders(<DHCPStatus id={vlan.id} />, { state });
    const dhcpStatus = screen.getByRole("region", { name: "DHCP" });

    expect(within(dhcpStatus).getByTestId("dhcp-status").textContent).toBe(
      "Disabled"
    );
  });

  it("renders correctly when a VLAN has external DHCP", () => {
    const vlan = factory.vlan({
      dhcp_on: false,
      external_dhcp: "192.168.1.1",
      relay_vlan: null,
    });
    const state = factory.rootState({
      vlan: factory.vlanState({ items: [vlan] }),
    });
    renderWithProviders(<DHCPStatus id={vlan.id} />, { state });
    const dhcpStatus = screen.getByRole("region", { name: "DHCP" });

    expect(within(dhcpStatus).getByTestId("dhcp-status").textContent).toBe(
      "External (192.168.1.1)"
    );
  });

  it("renders correctly when a VLAN has relayed DHCP", () => {
    const fabric = factory.fabric({ name: "fabrice" });
    const relayVLAN = factory.vlan({
      dhcp_on: true,
      fabric: fabric.id,
      name: "relay-vlan",
      vid: 101,
    });
    const vlan = factory.vlan({
      dhcp_on: false,
      external_dhcp: null,
      relay_vlan: relayVLAN.id,
    });
    const state = factory.rootState({
      fabric: factory.fabricState({ items: [fabric] }),
      vlan: factory.vlanState({ items: [vlan, relayVLAN] }),
    });
    renderWithProviders(<DHCPStatus id={vlan.id} />, { state });
    const dhcpStatus = screen.getByRole("region", { name: "DHCP" });

    expect(within(dhcpStatus).getByTestId("dhcp-status").textContent).toBe(
      "Relayed via fabrice.101 (relay-vlan)"
    );
  });

  it("renders correctly when a VLAN has MAAS-configured DHCP without high availability", () => {
    const controller = factory.controller({
      hostname: "primary-rack",
      system_id: "abc123",
    });
    const vlan = factory.vlan({
      dhcp_on: true,
      external_dhcp: null,
      primary_rack: "abc123",
      relay_vlan: null,
    });
    const state = factory.rootState({
      controller: factory.controllerState({ items: [controller] }),
      vlan: factory.vlanState({ items: [vlan] }),
    });
    renderWithProviders(<DHCPStatus id={vlan.id} />, { state });
    const dhcpStatus = screen.getByRole("region", { name: "DHCP" });

    expect(within(dhcpStatus).getByTestId("dhcp-status").textContent).toBe(
      "Enabled"
    );
    expect(
      within(dhcpStatus).getByTestId("high-availability").textContent
    ).toBe("No");
    expect(
      within(dhcpStatus).getByRole("link", { name: /primary-rack/i })
    ).toHaveAttribute(
      "href",

      urls.controllers.controller.index({ id: controller.system_id })
    );
  });

  it("renders correctly when a VLAN has MAAS-configured DHCP with high availability", () => {
    const primaryRack = factory.controller({
      hostname: "primary-rack",
      system_id: "abc123",
    });
    const secondaryRack = factory.controller({
      hostname: "secondary-rack",
      system_id: "def456",
    });
    const vlan = factory.vlan({
      dhcp_on: true,
      external_dhcp: null,
      primary_rack: "abc123",
      relay_vlan: null,
      secondary_rack: "def456",
    });
    const state = factory.rootState({
      controller: factory.controllerState({
        items: [primaryRack, secondaryRack],
      }),
      vlan: factory.vlanState({ items: [vlan] }),
    });
    renderWithProviders(<DHCPStatus id={vlan.id} />, { state });
    const dhcpStatus = screen.getByRole("region", { name: "DHCP" });

    expect(within(dhcpStatus).getByTestId("dhcp-status").textContent).toBe(
      "Enabled"
    );
    expect(
      within(dhcpStatus).getByTestId("high-availability").textContent
    ).toBe("Yes");
    expect(
      within(dhcpStatus).getByRole("link", { name: /primary-rack/i })
    ).toHaveAttribute(
      "href",

      urls.controllers.controller.index({ id: primaryRack.system_id })
    );
    expect(
      within(dhcpStatus).getByRole("link", { name: /secondary-rack/i })
    ).toHaveAttribute(
      "href",

      urls.controllers.controller.index({ id: secondaryRack.system_id })
    );
  });
});
