import ConfigureDHCP from "./ConfigureDHCP";

import { getSubnetDisplay } from "@/app/store/subnet/utils";
import { vlanActions } from "@/app/store/vlan";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

describe("ConfigureDHCP", () => {
  it("shows a spinner while data is loading", () => {
    const state = factory.rootState({
      fabric: factory.fabricState({ items: [], loading: true }),
      vlan: factory.vlanState({ items: [] }),
    });
    renderWithProviders(<ConfigureDHCP vlan={factory.vlan()} />, {
      state,
    });

    expect(screen.getByTestId("loading-data")).toBeInTheDocument();
  });

  it("correctly initialises data if the VLAN has DHCP from rack controllers", async () => {
    const primary = factory.controller({ system_id: "abc123" });
    const secondary = factory.controller({ system_id: "def456" });
    const vlan = factory.vlan({
      id: 1,
      primary_rack: primary.system_id,
      rack_sids: [primary.system_id, secondary.system_id],
      relay_vlan: null,
      secondary_rack: secondary.system_id,
    });
    const state = factory.rootState({
      controller: factory.controllerState({
        items: [primary, secondary, factory.controller(), factory.controller()],
      }),
      vlan: factory.vlanState({ items: [vlan] }),
    });
    renderWithProviders(<ConfigureDHCP vlan={vlan} />, {
      state,
    });

    // Wait for Formik validateOnMount to run.
    await waitFor(() => {
      expect(
        screen.getByRole("form", { name: "Configure DHCP" })
      ).toBeInTheDocument();
    });

    expect(
      screen.getByRole("radio", {
        name: "Provide DHCP from rack controller(s)",
      })
    ).toBeChecked();
    expect(
      screen.getByRole("radio", { name: "Relay to another VLAN" })
    ).not.toBeChecked();
    expect(screen.getByRole("combobox", { name: "Primary rack" })).toHaveValue(
      primary.system_id
    );
    expect(
      screen.getByRole("combobox", { name: "Secondary rack" })
    ).toHaveValue(secondary.system_id);
    expect(
      screen.queryByRole("combobox", { name: "VLAN" })
    ).not.toBeInTheDocument();
  });

  it("correctly initialises data if the VLAN has relayed DHCP", async () => {
    const relay = factory.vlan({ dhcp_on: true, id: 2 });
    const vlan = factory.vlan({
      id: 1,
      primary_rack: null,
      rack_sids: [],
      relay_vlan: relay.id,
      secondary_rack: null,
    });
    const state = factory.rootState({
      vlan: factory.vlanState({ items: [relay, vlan] }),
    });
    renderWithProviders(<ConfigureDHCP vlan={vlan} />, {
      state,
    });

    // Wait for Formik validateOnMount to run.
    await waitFor(() => {
      expect(
        screen.getByRole("form", { name: "Configure DHCP" })
      ).toBeInTheDocument();
    });

    expect(
      screen.getByRole("radio", { name: "Relay to another VLAN" })
    ).toBeChecked();
    expect(
      screen.getByRole("radio", {
        name: "Provide DHCP from rack controller(s)",
      })
    ).not.toBeChecked();
    expect(screen.getByRole("combobox", { name: "VLAN" })).toHaveValue(
      relay.id.toString()
    );
    expect(
      screen.queryByRole("combobox", { name: "Primary rack" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "Secondary rack" })
    ).not.toBeInTheDocument();
  });

  it("shows an error if no rack controllers are connected to the VLAN", async () => {
    const vlan = factory.vlan({
      id: 1,
      primary_rack: null,
      rack_sids: [],
      relay_vlan: null,
      secondary_rack: null,
    });
    const state = factory.rootState({
      vlan: factory.vlanState({ items: [vlan] }),
    });
    renderWithProviders(<ConfigureDHCP vlan={vlan} />, {
      state,
    });

    expect(
      screen.getByRole("form", { name: "Configure DHCP" })
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "This VLAN is not currently being utilised on any rack controller."
      )
    ).toBeInTheDocument();

    // Wait for Formik validateOnMount to run.
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Configure DHCP" })
      ).toBeDisabled();
    });
  });

  it(`shows an error if the subnet selected for reserving a dynamic range has no
    available IP addresses`, async () => {
    const relay = factory.vlan({ dhcp_on: true, id: 2 });
    const vlan = factory.vlan({
      id: 1,
      primary_rack: null,
      rack_sids: [],
      relay_vlan: relay.id,
      secondary_rack: null,
    });
    const subnet = factory.subnet({
      statistics: factory.subnetStatistics({ num_available: 0 }),
      vlan: vlan.id,
    });
    const state = factory.rootState({
      subnet: factory.subnetState({ items: [subnet], loaded: true }),
      vlan: factory.vlanState({ items: [vlan] }),
    });
    renderWithProviders(<ConfigureDHCP vlan={vlan} />, {
      state,
    });

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Subnet" }),
      subnet.id.toString()
    );
    await userEvent.tab();

    await waitFor(() => {
      expect(
        screen.getByText("This subnet has no available IP addresses.")
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole("button", { name: "Configure DHCP" })
    ).toBeDisabled();
  });

  it("shows a warning when attempting to disable DHCP on a VLAN", async () => {
    const vlan = factory.vlan({
      id: 1,
      primary_rack: null,
      rack_sids: [],
      relay_vlan: null,
      secondary_rack: null,
    });
    const state = factory.rootState({
      vlan: factory.vlanState({ items: [vlan] }),
    });
    renderWithProviders(<ConfigureDHCP vlan={vlan} />, {
      state,
    });

    await userEvent.click(
      screen.getByRole("checkbox", { name: "MAAS provides DHCP" })
    );

    expect(
      screen.getByText(
        "Are you sure you want to disable DHCP on this VLAN? All subnets on this VLAN will be affected."
      )
    ).toBeInTheDocument();
  });

  it("can configure DHCP with rack controllers", async () => {
    const primary = factory.controller({ system_id: "abc123" });
    const secondary = factory.controller({ system_id: "def456" });
    const vlan = factory.vlan({
      id: 1,
      primary_rack: null,
      rack_sids: [primary.system_id, secondary.system_id],
      relay_vlan: null,
      secondary_rack: null,
    });
    const subnet = factory.subnet({
      statistics: factory.subnetStatistics(),
      vlan: vlan.id,
    });

    const state = factory.rootState({
      subnet: factory.subnetState({ items: [subnet], loaded: true }),
      controller: factory.controllerState({
        items: [primary, secondary],
      }),
      vlan: factory.vlanState({ items: [vlan] }),
    });

    const { store } = renderWithProviders(<ConfigureDHCP vlan={vlan} />, {
      state,
    });

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Primary rack" }),
      primary.system_id
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Secondary rack" }),
      secondary.system_id
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Subnet" }),
      getSubnetDisplay(subnet)
    );
    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: "Start IP address" })
      ).toBeInTheDocument();
    });
    await userEvent.clear(
      screen.getByRole("textbox", { name: "Start IP address" })
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Start IP address" }),
      "192.168.1.1"
    );
    await userEvent.clear(
      screen.getByRole("textbox", { name: "End IP address" })
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "End IP address" }),
      "192.168.1.5"
    );
    await userEvent.clear(screen.getByRole("textbox", { name: "Gateway IP" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "Gateway IP" }),
      "192.168.1.6"
    );
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Configure DHCP" })
      ).not.toBeDisabled();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Configure DHCP" })
    );
    const expectedAction = vlanActions.configureDHCP({
      controllers: [primary.system_id, secondary.system_id],
      extra: {
        end: "192.168.1.5",
        gateway: "192.168.1.6",
        start: "192.168.1.1",
        subnet: subnet.id,
      },
      id: vlan.id,
      relay_vlan: null,
    });

    await waitFor(() => {
      const actualAction = store
        .getActions()
        .find((action) => action.type === expectedAction.type);
      expect(actualAction).toStrictEqual(expectedAction);
    });
  });

  it("displays an error when no subnet is selected", async () => {
    const primary = factory.controller({ system_id: "abc123" });
    const secondary = factory.controller({ system_id: "def456" });
    const vlan = factory.vlan({
      id: 1,
      primary_rack: null,
      rack_sids: [primary.system_id, secondary.system_id],
      relay_vlan: null,
      secondary_rack: null,
    });
    const subnet = factory.subnet({
      statistics: factory.subnetStatistics(),
      vlan: vlan.id,
    });

    const state = factory.rootState({
      subnet: factory.subnetState({ items: [subnet], loaded: true }),
      controller: factory.controllerState({
        items: [primary, secondary],
      }),
      vlan: factory.vlanState({ items: [vlan] }),
    });
    renderWithProviders(<ConfigureDHCP vlan={vlan} />, {
      state,
    });

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Subnet" }),
      "Select subnet"
    );
    await userEvent.tab();
    expect(screen.getByText(/Subnet is required/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Configure DHCP" })
    ).toBeDisabled();
  });

  it("can configure relayed DHCP", async () => {
    const relay = factory.vlan({ dhcp_on: true, id: 2 });
    const vlan = factory.vlan({
      id: 1,
      primary_rack: null,
      rack_sids: [],
      relay_vlan: null,
      secondary_rack: null,
    });
    const state = factory.rootState({
      vlan: factory.vlanState({ items: [relay, vlan] }),
    });

    const { store } = renderWithProviders(<ConfigureDHCP vlan={vlan} />, {
      state,
    });

    await userEvent.click(
      screen.getByRole("radio", { name: "Relay to another VLAN" })
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "VLAN" }),
      relay.name
    );
    await userEvent.tab();

    expect(
      screen.getByRole("button", { name: "Configure DHCP" })
    ).toBeEnabled();
    await userEvent.click(
      screen.getByRole("button", { name: "Configure DHCP" })
    );

    const expectedAction = vlanActions.configureDHCP({
      controllers: [],
      id: vlan.id,
      relay_vlan: relay.id,
    });

    await waitFor(() => {
      const actualAction = store
        .getActions()
        .find((action) => action.type === expectedAction.type);
      expect(actualAction).toStrictEqual(expectedAction);
    });
  });

  it("can configure DHCP while also defining a dynamic IP range", async () => {
    const relay = factory.vlan({ dhcp_on: true, id: 2 });
    const vlan = factory.vlan({
      id: 1,
      primary_rack: null,
      rack_sids: [],
      relay_vlan: null,
      secondary_rack: null,
    });
    const subnet = factory.subnet({ vlan: vlan.id });
    const state = factory.rootState({
      iprange: factory.ipRangeState({ items: [] }),
      subnet: factory.subnetState({ items: [subnet], loaded: true }),
      vlan: factory.vlanState({ items: [relay, vlan] }),
    });

    const { store } = renderWithProviders(<ConfigureDHCP vlan={vlan} />, {
      state,
    });

    await userEvent.click(
      screen.getByRole("radio", { name: "Relay to another VLAN" })
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "VLAN" }),
      relay.name
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Subnet" }),
      getSubnetDisplay(subnet)
    );

    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: "Start IP address" })
      ).toBeInTheDocument();
    });
    await userEvent.clear(
      screen.getByRole("textbox", { name: "Start IP address" })
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Start IP address" }),
      "192.168.1.1"
    );
    await userEvent.clear(
      screen.getByRole("textbox", { name: "End IP address" })
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "End IP address" }),
      "192.168.1.5"
    );
    await userEvent.clear(screen.getByRole("textbox", { name: "Gateway IP" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "Gateway IP" }),
      "192.168.1.6"
    );
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Configure DHCP" })
      ).not.toBeDisabled();
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Configure DHCP" })
    );

    const expectedAction = vlanActions.configureDHCP({
      controllers: [],
      extra: {
        end: "192.168.1.5",
        gateway: "192.168.1.6",
        start: "192.168.1.1",
        subnet: subnet.id,
      },
      id: vlan.id,
      relay_vlan: relay.id,
    });

    await waitFor(() => {
      const actualAction = store
        .getActions()
        .find((action) => action.type === expectedAction.type);

      expect(actualAction).toStrictEqual(expectedAction);
    });
  });
});
