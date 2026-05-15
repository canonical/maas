import { Formik } from "formik";

import { LinkMonitoring, MacSource } from "../types";

import BondFormFields from "./BondFormFields";

import {
  BondLacpRate,
  BondMode,
  BondXmitHashPolicy,
} from "@/app/store/general/types";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("BondFormFields", () => {
  let state: RootState;
  const initialValues = {
    bond_downdelay: 0,
    bond_lacp_rate: "",
    bond_miimon: 0,
    bond_mode: BondMode.ACTIVE_BACKUP,
    bond_updelay: 0,
    bond_xmit_hash_policy: "",
    fabric: "",
    ip_address: "",
    linkMonitoring: "",
    mac_address: "",
    macSource: MacSource.MANUAL,
    macNic: "",
    mode: "",
    name: "",
    subnet: "",
    tags: [],
    vlan: "",
  };
  beforeEach(() => {
    state = factory.rootState({
      general: factory.generalState({
        bondOptions: factory.bondOptionsState({
          data: factory.bondOptions({
            lacp_rates: [
              [BondLacpRate.FAST, BondLacpRate.FAST],
              [BondLacpRate.SLOW, BondLacpRate.SLOW],
            ],
            modes: [
              [BondMode.BALANCE_RR, BondMode.BALANCE_RR],
              [BondMode.ACTIVE_BACKUP, BondMode.ACTIVE_BACKUP],
              [BondMode.BALANCE_XOR, BondMode.BALANCE_XOR],
              [BondMode.BROADCAST, BondMode.BROADCAST],
              [BondMode.LINK_AGGREGATION, BondMode.LINK_AGGREGATION],
              [BondMode.BALANCE_TLB, BondMode.BALANCE_TLB],
              [BondMode.BALANCE_ALB, BondMode.BALANCE_ALB],
            ],
            xmit_hash_policies: [
              [BondXmitHashPolicy.LAYER2, BondXmitHashPolicy.LAYER2],
              [BondXmitHashPolicy.LAYER2_3, BondXmitHashPolicy.LAYER2_3],
              [BondXmitHashPolicy.LAYER3_4, BondXmitHashPolicy.LAYER3_4],
              [BondXmitHashPolicy.ENCAP2_3, BondXmitHashPolicy.ENCAP2_3],
              [BondXmitHashPolicy.ENCAP3_4, BondXmitHashPolicy.ENCAP3_4],
            ],
          }),
          loaded: true,
        }),
      }),
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            system_id: "abc123",
            interfaces: [
              factory.machineInterface({
                id: 17,
                type: NetworkInterfaceTypes.PHYSICAL,
                mac_address: "6a:6e:4a:29:a5:42",
              }),
            ],
          }),
        ],
        loaded: true,
      }),
    });
  });

  it("does not display the hash policy field by default", async () => {
    renderWithProviders(
      <Formik initialValues={initialValues} onSubmit={vi.fn()}>
        <BondFormFields selected={[]} systemId="abc123" />
      </Formik>,
      { state }
    );

    expect(
      screen.queryByRole("combobox", { name: "Hash policy" })
    ).not.toBeInTheDocument();
  });

  it("displays the hash policy field for some bond modes", async () => {
    renderWithProviders(
      <Formik initialValues={initialValues} onSubmit={vi.fn()}>
        <BondFormFields selected={[]} systemId="abc123" />
      </Formik>,
      { state }
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Bond mode" }),
      BondMode.BALANCE_XOR
    );

    expect(
      screen.getByRole("combobox", { name: "Hash policy" })
    ).toBeInTheDocument();
  });

  it("does not display the lacp rate field by default", async () => {
    renderWithProviders(
      <Formik initialValues={initialValues} onSubmit={vi.fn()}>
        <BondFormFields selected={[]} systemId="abc123" />
      </Formik>,
      { state }
    );

    expect(
      screen.queryByRole("combobox", { name: "LACP rate" })
    ).not.toBeInTheDocument();
  });

  it("displays the lacp rate field for some bond modes", async () => {
    renderWithProviders(
      <Formik initialValues={initialValues} onSubmit={vi.fn()}>
        <BondFormFields selected={[]} systemId="abc123" />
      </Formik>,
      { state }
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Bond mode" }),
      BondMode.LINK_AGGREGATION
    );

    expect(
      screen.getByRole("combobox", { name: "LACP rate" })
    ).toBeInTheDocument();
  });

  it("does not display the monitoring fields by default", async () => {
    renderWithProviders(
      <Formik initialValues={initialValues} onSubmit={vi.fn()}>
        <BondFormFields selected={[]} systemId="abc123" />
      </Formik>,
      { state }
    );

    const monitoringFieldNames = [
      "Monitoring frequency (ms)",
      "Updelay (ms)",
      "Downdelay (ms)",
    ];

    monitoringFieldNames.forEach((field) => {
      expect(
        screen.queryByRole("textbox", { name: field })
      ).not.toBeInTheDocument();
    });
  });

  it("displays the monitoring fields when link monitoring is set", async () => {
    renderWithProviders(
      <Formik initialValues={initialValues} onSubmit={vi.fn()}>
        <BondFormFields selected={[]} systemId="abc123" />
      </Formik>,
      { state }
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Link monitoring" }),
      LinkMonitoring.MII
    );

    const monitoringFieldNames = [
      "Monitoring frequency (ms)",
      "Updelay (ms)",
      "Downdelay (ms)",
    ];

    monitoringFieldNames.forEach((field) => {
      expect(screen.getByRole("textbox", { name: field })).toBeInTheDocument();
    });
  });

  it("sets the mac address field when the nic field changes", async () => {
    renderWithProviders(
      <Formik initialValues={initialValues} onSubmit={vi.fn()}>
        <BondFormFields selected={[{ nicId: 17 }]} systemId="abc123" />
      </Formik>,
      { state }
    );
    await userEvent.click(
      screen.getByRole("radio", { name: "Use MAC address from bond member" })
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "bond member" }),
      "6a:6e:4a:29:a5:42"
    );
    expect(screen.getByRole("textbox", { name: "MAC address" })).toHaveValue(
      "6a:6e:4a:29:a5:42"
    );
  });

  it("enables the mac address field when the radio is changed to manual", async () => {
    renderWithProviders(
      <Formik initialValues={initialValues} onSubmit={vi.fn()}>
        <BondFormFields selected={[]} systemId="abc123" />
      </Formik>,
      { state }
    );
    await userEvent.click(
      screen.getByRole("radio", { name: "Manual MAC address" })
    );

    expect(
      screen.getByRole("textbox", { name: "MAC address" })
    ).not.toBeDisabled();
    expect(
      screen.getByRole("combobox", { name: "bond member" })
    ).toBeDisabled();
  });

  it("enables the mac nic field when the radio is changed to 'nic'", async () => {
    renderWithProviders(
      <Formik initialValues={initialValues} onSubmit={vi.fn()}>
        <BondFormFields selected={[]} systemId="abc123" />
      </Formik>,
      { state }
    );
    await userEvent.click(
      screen.getByRole("radio", { name: "Use MAC address from bond member" })
    );

    expect(screen.getByRole("textbox", { name: "MAC address" })).toBeDisabled();
    expect(
      screen.getByRole("combobox", { name: "bond member" })
    ).not.toBeDisabled();
  });

  it("resets the mac address field when the radio is changed to 'nic'", async () => {
    renderWithProviders(
      <Formik
        initialValues={{
          ...initialValues,
          macNic: "6a:6e:4a:29:a5:42",
          mac_address: "",
        }}
        onSubmit={vi.fn()}
      >
        <BondFormFields selected={[]} systemId="abc123" />
      </Formik>,
      { state }
    );
    // Enable the mac address field so it can be changed.
    await userEvent.click(
      screen.getByRole("radio", { name: "Manual MAC address" })
    );

    // Change the mac address.
    await userEvent.type(
      screen.getByRole("textbox", { name: "MAC address" }),
      "11:11:11:11:11:11"
    );

    // Enable the nic select again
    await userEvent.click(
      screen.getByRole("radio", { name: "Use MAC address from bond member" })
    );
    // The mac address field should be updated to the nic select value.
    expect(screen.getByRole("textbox", { name: "MAC address" })).toHaveValue(
      "6a:6e:4a:29:a5:42"
    );
  });
});
