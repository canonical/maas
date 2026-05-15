import { screen } from "@testing-library/react";
import { Formik } from "formik";

import SubnetSelect from "./SubnetSelect";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

describe("SubnetSelect", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      subnet: factory.subnetState({
        items: [
          factory.subnet({
            id: 1,
            name: "sub1",
            cidr: "172.16.1.0/24",
            vlan: 3,
          }),
          factory.subnet({
            id: 2,
            name: "sub2",
            cidr: "172.16.2.0/24",
            vlan: 4,
          }),
        ],
        loaded: true,
      }),
    });
  });

  it("shows a spinner if the subnets haven’t loaded", () => {
    state.subnet.loaded = false;

    renderWithProviders(
      <Formik initialValues={{ subnet: "" }} onSubmit={vi.fn()}>
        <SubnetSelect name="subnet" />
      </Formik>,
      { state }
    );
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("displays the subnet options", () => {
    renderWithProviders(
      <Formik initialValues={{ subnet: "" }} onSubmit={vi.fn()}>
        <SubnetSelect name="subnet" />
      </Formik>,
      { state }
    );
    expect(screen.getByRole("combobox")).toHaveTextContent("Select subnet");
    expect(screen.getByRole("combobox")).toHaveTextContent(
      "172.16.1.0/24 (sub1)"
    );
    expect(screen.getByRole("combobox")).toHaveTextContent(
      "172.16.2.0/24 (sub2)"
    );
  });

  it("can display a default option", () => {
    const defaultOption = {
      label: "Default",
      value: "99",
    };
    renderWithProviders(
      <Formik initialValues={{ subnet: "" }} onSubmit={vi.fn()}>
        <SubnetSelect defaultOption={defaultOption} name="subnet" />
      </Formik>,
      { state }
    );
    expect(screen.getByRole("combobox").childNodes[0]).toHaveTextContent(
      "Default"
    );
  });

  it("can hide the default option", () => {
    state.subnet.items = [];

    renderWithProviders(
      <Formik initialValues={{ subnet: "" }} onSubmit={vi.fn()}>
        <SubnetSelect defaultOption={null} name="subnet" />
      </Formik>,
      { state }
    );
    expect(
      screen.queryByRole("option", { name: "Default" })
    ).not.toBeInTheDocument();
  });

  it("filter the subnets by vlan", () => {
    renderWithProviders(
      <Formik initialValues={{ subnet: "" }} onSubmit={vi.fn()}>
        <SubnetSelect name="subnet" vlan={3} />
      </Formik>,
      { state }
    );
    expect(screen.getByRole("combobox")).toHaveTextContent(
      "172.16.1.0/24 (sub1)"
    );
    expect(
      screen.queryByRole("option", { name: "172.16.2.0/24 (sub2)" })
    ).not.toBeInTheDocument();
  });

  it("can filter the subnets using a provided function", () => {
    renderWithProviders(
      <Formik initialValues={{ subnet: "" }} onSubmit={vi.fn()}>
        <SubnetSelect
          filterFunction={(subnet) => subnet.vlan === 4}
          name="subnet"
        />
      </Formik>,
      { state }
    );
    expect(screen.getByRole("combobox")).toHaveTextContent(
      "172.16.2.0/24 (sub2)"
    );
    expect(
      screen.queryByRole("option", { name: "172.16.1.0/24 (sub1)" })
    ).not.toBeInTheDocument();
  });

  it("orders the subnets by name", () => {
    state.subnet.items = [
      factory.subnet({
        id: 1,
        name: "sub1",
        cidr: "1.1.1.1/24",
        vlan: 3,
      }),
      factory.subnet({
        id: 2,
        name: "sub2",
        cidr: "0.0.0.0/24",
        vlan: 4,
      }),
    ];

    renderWithProviders(
      <Formik initialValues={{ subnet: "" }} onSubmit={vi.fn()}>
        <SubnetSelect name="subnet" />
      </Formik>,
      { state }
    );
    expect(screen.getByRole("combobox")).toHaveTextContent("0.0.0.0/24 (sub2)");
    expect(screen.getByRole("combobox")).toHaveTextContent("1.1.1.1/24 (sub1)");
  });
});
