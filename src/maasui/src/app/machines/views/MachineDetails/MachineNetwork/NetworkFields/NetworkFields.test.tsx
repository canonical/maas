import { Formik } from "formik";

import NetworkFields, {
  Label as NetworkFieldsLabel,
  networkFieldsInitialValues,
} from "./NetworkFields";

import { Label as FabricSelectLabel } from "@/app/base/components/FabricSelect/FabricSelect";
import { Label as LinkModeSelectLabel } from "@/app/base/components/LinkModeSelect/LinkModeSelect";
import { Label as SubnetSelectLabel } from "@/app/base/components/SubnetSelect/SubnetSelect";
import { Label as VLANSelectLabel } from "@/app/base/components/VLANSelect/VLANSelect";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes, NetworkLinkMode } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  within,
  renderWithProviders,
} from "@/testing/utils";

describe("NetworkFields", () => {
  let state: RootState;

  beforeEach(() => {
    const vlan = factory.vlan({ fabric: 1, vid: 1 });
    state = factory.rootState({
      fabric: factory.fabricState({
        items: [
          factory.fabric({ id: 1, default_vlan_id: vlan.id }),
          factory.fabric({ default_vlan_id: vlan.id }),
        ],
        loaded: true,
      }),
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
      subnet: factory.subnetState({
        items: [
          factory.subnet({ vlan: vlan.id }),
          factory.subnet({ vlan: vlan.id }),
        ],
        loaded: true,
      }),
      vlan: factory.vlanState({
        items: [vlan, factory.vlan({ fabric: 1, vid: 2 })],
        loaded: true,
      }),
    });
  });

  it("changes the vlan to the default for a fabric", async () => {
    const fabric = factory.fabric();
    state.vlan.items = [
      factory.vlan({ fabric: fabric.id, vid: 1 }),
      factory.vlan({ fabric: fabric.id, vid: 2 }),
    ];
    fabric.default_vlan_id = state.vlan.items[1].id;
    state.fabric.items = [fabric];

    renderWithProviders(
      <Formik initialValues={networkFieldsInitialValues} onSubmit={vi.fn()}>
        <NetworkFields interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Formik>,
      { state, initialEntries: ["/machine/abc123"] }
    );
    const vlanSelect = screen.getByRole("combobox", {
      name: VLANSelectLabel.Select,
    });
    await waitFor(() => {
      expect(
        within(vlanSelect).getByRole("option", { selected: true })
      ).toHaveAttribute("value", state.vlan.items[0].id.toString());
    });
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: FabricSelectLabel.Select }),
      fabric.id.toString()
    );
    await waitFor(() => {
      expect(
        within(vlanSelect).getByRole("option", { selected: true })
      ).toHaveAttribute("value", state.vlan.items[1].id.toString());
    });
  });

  it("resets all fields after vlan when the fabric is changed", async () => {
    renderWithProviders(
      <Formik initialValues={networkFieldsInitialValues} onSubmit={vi.fn()}>
        <NetworkFields interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Formik>,
      { state, initialEntries: ["/machine/abc123"] }
    );
    const subnetSelect = screen.getByRole("combobox", {
      name: SubnetSelectLabel.Select,
    });
    await waitFor(() => {
      expect(
        within(subnetSelect).getByRole("option", { selected: true })
      ).toHaveAttribute("value", "");
    });
    // Set the values of the fields so they're all visible and have values.
    await userEvent.selectOptions(
      subnetSelect,
      state.subnet.items[1].id.toString()
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: LinkModeSelectLabel.Select }),
      NetworkLinkMode.STATIC
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: NetworkFieldsLabel.IPAddress }),
      "1.2.3.4"
    );
    // Change the fabric and the other fields should reset.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: FabricSelectLabel.Select }),
      state.fabric.items[1].id.toString()
    );
    await waitFor(() => {
      expect(
        screen.queryByRole("combobox", { name: LinkModeSelectLabel.Select })
      ).not.toBeInTheDocument();
    });
    await waitFor(() => {
      expect(
        screen.queryByRole("textbox", { name: NetworkFieldsLabel.IPAddress })
      ).not.toBeInTheDocument();
    });
    await waitFor(() => {
      expect(
        within(subnetSelect).getByRole("option", { selected: true })
      ).toHaveAttribute("value", "");
    });
  });

  it("resets all fields after vlan when it is changed", async () => {
    renderWithProviders(
      <Formik initialValues={networkFieldsInitialValues} onSubmit={vi.fn()}>
        <NetworkFields interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Formik>,
      { state, initialEntries: ["/machine/abc123"] }
    );
    // Set the values of the fields so they're all visible and have values.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: SubnetSelectLabel.Select }),
      state.subnet.items[1].id.toString()
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: LinkModeSelectLabel.Select }),
      NetworkLinkMode.STATIC
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: NetworkFieldsLabel.IPAddress }),
      "1.2.3.4"
    );
    // Change the VLAN and the other fields should reset.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: VLANSelectLabel.Select }),
      state.vlan.items[1].id.toString()
    );
    const subnetSelect = screen.getByRole("combobox", {
      name: SubnetSelectLabel.Select,
    });
    await waitFor(() => {
      expect(
        within(subnetSelect).getByRole("option", { selected: true })
      ).toHaveAttribute("value", "");
    });
    expect(
      screen.queryByRole("combobox", { name: LinkModeSelectLabel.Select })
    ).not.toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.queryByRole("textbox", { name: NetworkFieldsLabel.IPAddress })
      ).not.toBeInTheDocument();
    });
  });

  it("resets all fields after subnet when it is changed", async () => {
    renderWithProviders(
      <Formik initialValues={networkFieldsInitialValues} onSubmit={vi.fn()}>
        <NetworkFields interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Formik>,
      { state, initialEntries: ["/machine/abc123"] }
    );
    // Set the values of the fields so they're all visible and have values.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: SubnetSelectLabel.Select }),
      state.subnet.items[1].id.toString()
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: LinkModeSelectLabel.Select }),
      NetworkLinkMode.STATIC
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: NetworkFieldsLabel.IPAddress }),
      "1.2.3.4"
    );
    // Change the subnet and the other fields should reset.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: SubnetSelectLabel.Select }),
      ""
    );
    expect(
      screen.queryByRole("combobox", { name: LinkModeSelectLabel.Select })
    ).not.toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.queryByRole("textbox", { name: NetworkFieldsLabel.IPAddress })
      ).not.toBeInTheDocument();
    });
  });

  it("sets the ip address to the first address from the subnet when the mode is static", async () => {
    state.subnet.items.push(
      factory.subnet({
        statistics: factory.subnetStatistics({
          first_address: "1.2.3.4",
        }),
        vlan: state.vlan.items[0].id,
      })
    );

    renderWithProviders(
      <Formik initialValues={networkFieldsInitialValues} onSubmit={vi.fn()}>
        <NetworkFields interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Formik>,
      { state, initialEntries: ["/machine/abc123"] }
    );
    // Set the values of the fields so they're all visible and have values.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: SubnetSelectLabel.Select }),
      state.subnet.items[2].id.toString()
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: LinkModeSelectLabel.Select }),
      NetworkLinkMode.STATIC
    );
    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: NetworkFieldsLabel.IPAddress })
      ).toHaveAttribute("value", "1.2.3.4");
    });
  });

  it("does not display the mode field if a subnet has not been chosen", async () => {
    renderWithProviders(
      <Formik initialValues={networkFieldsInitialValues} onSubmit={vi.fn()}>
        <NetworkFields interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Formik>,
      { state, initialEntries: ["/machine/abc123"] }
    );
    expect(
      screen.queryByRole("combobox", { name: LinkModeSelectLabel.Select })
    ).not.toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.queryByRole("textbox", { name: NetworkFieldsLabel.IPAddress })
      ).not.toBeInTheDocument();
    });
  });

  it("displays the mode field if a subnet has been chosen", async () => {
    renderWithProviders(
      <Formik initialValues={networkFieldsInitialValues} onSubmit={vi.fn()}>
        <NetworkFields interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Formik>,
      { state, initialEntries: ["/machine/abc123"] }
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: SubnetSelectLabel.Select }),
      state.subnet.items[1].id.toString()
    );
    expect(
      screen.getByRole("combobox", { name: LinkModeSelectLabel.Select })
    ).toBeInTheDocument();
    const linkModeSelect = screen.getByRole("combobox", {
      name: LinkModeSelectLabel.Select,
    });
    await waitFor(() => {
      expect(
        within(linkModeSelect).getByRole("option", { selected: true })
      ).toHaveAttribute("value", NetworkLinkMode.LINK_UP);
    });
  });

  it("reset the mode field to 'auto' when editing and changed subnet", async () => {
    renderWithProviders(
      <Formik initialValues={networkFieldsInitialValues} onSubmit={vi.fn()}>
        <NetworkFields editing interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Formik>,
      { state, initialEntries: ["/machine/abc123"] }
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: SubnetSelectLabel.Select }),
      state.subnet.items[1].id.toString()
    );
    expect(
      screen.getByRole("combobox", { name: LinkModeSelectLabel.Select })
    ).toBeInTheDocument();
    const linkModeSelect = screen.getByRole("combobox", {
      name: LinkModeSelectLabel.Select,
    });
    await waitFor(() => {
      expect(
        within(linkModeSelect).getByRole("option", { selected: true })
      ).toHaveAttribute("value", NetworkLinkMode.AUTO);
    });
  });

  it("reset the mode field to 'unconfigured' when editing and removed subnet", async () => {
    const onSubmit = vi.fn();
    renderWithProviders(
      <Formik
        initialValues={{
          ...networkFieldsInitialValues,
          mode: NetworkLinkMode.AUTO,
        }}
        onSubmit={onSubmit}
      >
        {({ handleSubmit }) => (
          <form aria-label="test form" onSubmit={handleSubmit}>
            <NetworkFields
              editing
              interfaceType={NetworkInterfaceTypes.PHYSICAL}
            />
            <button type="submit">Save</button>
          </form>
        )}
      </Formik>,
      { state, initialEntries: ["/machine/abc123"] }
    );
    // Remove the subnet.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: SubnetSelectLabel.Select }),
      ""
    );
    expect(
      screen.queryByRole("combobox", { name: LinkModeSelectLabel.Select })
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(onSubmit.mock.calls[0][0].mode).toBe(NetworkLinkMode.LINK_UP);
    });
  });

  it("does not display the ip address field if the mode has not been chosen", async () => {
    renderWithProviders(
      <Formik initialValues={networkFieldsInitialValues} onSubmit={vi.fn()}>
        <NetworkFields interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Formik>,
      { state, initialEntries: ["/machine/abc123"] }
    );
    await waitFor(() => {
      expect(
        screen.queryByRole("textbox", { name: NetworkFieldsLabel.IPAddress })
      ).not.toBeInTheDocument();
    });
  });

  it("does not display the ip address field if the chosen mode is not static", async () => {
    renderWithProviders(
      <Formik initialValues={networkFieldsInitialValues} onSubmit={vi.fn()}>
        <NetworkFields interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Formik>,
      { state, initialEntries: ["/machine/abc123"] }
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: SubnetSelectLabel.Select }),
      state.subnet.items[1].id.toString()
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: LinkModeSelectLabel.Select }),
      NetworkLinkMode.AUTO
    );
    await waitFor(() => {
      expect(
        screen.queryByRole("textbox", { name: NetworkFieldsLabel.IPAddress })
      ).not.toBeInTheDocument();
    });
  });

  it("displays the ip address field if the mode is static", async () => {
    renderWithProviders(
      <Formik initialValues={networkFieldsInitialValues} onSubmit={vi.fn()}>
        <NetworkFields interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Formik>,
      { state, initialEntries: ["/machine/abc123"] }
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: SubnetSelectLabel.Select }),
      state.subnet.items[1].id.toString()
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: LinkModeSelectLabel.Select }),
      NetworkLinkMode.STATIC
    );
    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: NetworkFieldsLabel.IPAddress })
      ).toBeInTheDocument();
    });
  });
});
