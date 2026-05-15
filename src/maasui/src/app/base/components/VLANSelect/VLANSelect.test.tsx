import { Formik } from "formik";

import VLANSelect from "./VLANSelect";

import type { RootState } from "@/app/store/root/types";
import { VlanVid } from "@/app/store/vlan/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, within } from "@/testing/utils";

describe("VLANSelect", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      vlan: factory.vlanState({
        items: [
          factory.vlan({ id: 1, name: "vlan1", vid: 1, fabric: 3 }),
          factory.vlan({ id: 2, name: "vlan2", vid: 2, fabric: 4 }),
        ],
        loaded: true,
      }),
    });
  });

  it("shows a spinner if the vlans haven't loaded", () => {
    state.vlan.loaded = false;
    renderWithProviders(
      <Formik initialValues={{ vlan: "" }} onSubmit={vi.fn()}>
        <VLANSelect name="vlan" showSpinnerOnLoad />
      </Formik>,
      { state }
    );

    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("displays the vlan options", () => {
    renderWithProviders(
      <Formik initialValues={{ vlan: "" }} onSubmit={vi.fn()}>
        <VLANSelect name="vlan" />
      </Formik>,
      { state }
    );
    const options = within(
      screen.getByRole("combobox", { name: "VLAN" })
    ).getAllByRole("option");

    expect(options[1]).toHaveValue("1");
    expect(options[1]).toHaveTextContent("1 (vlan1)");

    expect(options[2]).toHaveValue("2");
    expect(options[2]).toHaveTextContent("2 (vlan2)");
  });

  it("can display a default option", () => {
    const defaultOption = {
      label: "Default",
      value: "99",
    };
    renderWithProviders(
      <Formik initialValues={{ vlan: "" }} onSubmit={vi.fn()}>
        <VLANSelect defaultOption={defaultOption} name="vlan" />
      </Formik>,
      { state }
    );

    const options = within(
      screen.getByRole("combobox", { name: "VLAN" })
    ).getAllByRole("option");
    expect(options[0]).toHaveValue("99");
    expect(options[0]).toHaveTextContent("Default");
  });

  it("can hide the default option", () => {
    state.vlan.items = [];
    renderWithProviders(
      <Formik initialValues={{ vlan: "" }} onSubmit={vi.fn()}>
        <VLANSelect defaultOption={null} name="vlan" />
      </Formik>,
      { state }
    );
    expect(screen.queryByRole("option")).not.toBeInTheDocument();
  });

  it("filter the vlans by fabric", () => {
    renderWithProviders(
      <Formik initialValues={{ vlan: "" }} onSubmit={vi.fn()}>
        <VLANSelect fabric={3} name="vlan" />
      </Formik>,
      { state }
    );
    const options = within(
      screen.getByRole("combobox", { name: "VLAN" })
    ).getAllByRole("option");

    expect(options[1]).toHaveValue("1");
    expect(options[1]).toHaveTextContent("1 (vlan1)");

    expect(
      screen.queryByRole("option", { name: "2 (vlan2)" })
    ).not.toBeInTheDocument();
  });

  it("can not show the default VLAN", () => {
    state.vlan.items = [
      factory.vlan({ id: 1, name: "vlan1", vid: 0, fabric: 3 }),
      factory.vlan({ id: 2, name: "vlan2", vid: 2, fabric: 4 }),
    ];
    renderWithProviders(
      <Formik initialValues={{ vlan: "" }} onSubmit={vi.fn()}>
        <VLANSelect includeDefaultVlan={false} name="vlan" />
      </Formik>,
      { state }
    );

    const options = within(
      screen.getByRole("combobox", { name: "VLAN" })
    ).getAllByRole("option");

    expect(options[1]).toHaveValue("2");
    expect(options[1]).toHaveTextContent("2 (vlan2)");

    expect(
      screen.queryByRole("option", { name: "1 (vlan1)" })
    ).not.toBeInTheDocument();
  });

  it("can generate the vlan names", () => {
    renderWithProviders(
      <Formik initialValues={{ vlan: "" }} onSubmit={vi.fn()}>
        <VLANSelect generateName={(vlan) => `name: ${vlan.name}`} name="vlan" />
      </Formik>,
      { state }
    );
    const options = within(
      screen.getByRole("combobox", { name: "VLAN" })
    ).getAllByRole("option");

    expect(options[1]).toHaveValue("2");
    expect(options[1]).toHaveTextContent("name: vlan2");

    expect(options[2]).toHaveValue("1");
    expect(options[2]).toHaveTextContent("name: vlan1");
  });

  it("orders the vlans by name", () => {
    state.vlan.items = [
      factory.vlan({ id: 1, name: "vlan1", vid: 21, fabric: 3 }),
      factory.vlan({ id: 2, name: "vlan2", vid: 2, fabric: 4 }),
    ];
    renderWithProviders(
      <Formik initialValues={{ vlan: "" }} onSubmit={vi.fn()}>
        <VLANSelect name="vlan" />
      </Formik>,
      { state }
    );
    const options = within(
      screen.getByRole("combobox", { name: "VLAN" })
    ).getAllByRole("option");

    expect(options[1]).toHaveValue("2");
    expect(options[1]).toHaveTextContent("2 (vlan2)");

    expect(options[2]).toHaveValue("1");
    expect(options[2]).toHaveTextContent("21 (vlan1)");
  });

  it("orders untagged vlans to the start", () => {
    state.vlan.items = [
      factory.vlan({ id: 1, name: "vlan1", vid: 21, fabric: 3 }),
      factory.vlan({ id: 2, vid: VlanVid.UNTAGGED, fabric: 4 }),
    ];
    renderWithProviders(
      <Formik initialValues={{ vlan: "" }} onSubmit={vi.fn()}>
        <VLANSelect name="vlan" />
      </Formik>,
      { state }
    );
    const options = within(
      screen.getByRole("combobox", { name: "VLAN" })
    ).getAllByRole("option");

    expect(options[1]).toHaveValue("2");
    expect(options[1]).toHaveTextContent("untagged");

    expect(options[2]).toHaveValue("1");
    expect(options[2]).toHaveTextContent("21 (vlan1)");
  });
});
