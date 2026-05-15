import { Formik } from "formik";

import AddDeviceInterfaces from "../AddDeviceInterfaces";
import type { AddDeviceInterface } from "../types";

import { DeviceIpAssignment } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  renderWithProviders,
  within,
} from "@/testing/utils";

describe("AddDeviceInterfaces", () => {
  let interfaces: AddDeviceInterface[];
  let state: RootState;

  beforeEach(() => {
    interfaces = [
      {
        id: 0,
        ip_address: "",
        ip_assignment: DeviceIpAssignment.DYNAMIC,
        mac: "",
        name: "eth0",
        subnet: "",
        subnet_cidr: "",
      },
    ];
    state = factory.rootState({
      subnet: factory.subnetState({
        items: [factory.subnet({ id: 0, name: "default" })],
        loaded: true,
      }),
    });
  });

  it("does not show subnet or IP address fields for dynamic IP assignment", () => {
    interfaces[0].ip_assignment = DeviceIpAssignment.DYNAMIC;

    renderWithProviders(
      <Formik initialValues={{ interfaces }} onSubmit={vi.fn()}>
        <AddDeviceInterfaces />
      </Formik>,
      { state }
    );

    expect(screen.queryByTestId("subnet-field")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ip-address-field")).not.toBeInTheDocument();
  });

  it("shows the standard IP address field for external IP assignment", () => {
    interfaces[0].ip_assignment = DeviceIpAssignment.EXTERNAL;

    renderWithProviders(
      <Formik initialValues={{ interfaces }} onSubmit={vi.fn()}>
        <AddDeviceInterfaces />
      </Formik>,
      { state }
    );

    expect(screen.getByTestId("ip-address-field")).toBeInTheDocument();

    expect(screen.queryByTestId("subnet-field")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("prefixed-ip-address-field")
    ).not.toBeInTheDocument();
  });

  it("shows the subnet field when static IP assignment is selected", () => {
    interfaces[0].ip_assignment = DeviceIpAssignment.STATIC;

    renderWithProviders(
      <Formik initialValues={{ interfaces }} onSubmit={vi.fn()}>
        <AddDeviceInterfaces />
      </Formik>,
      { state }
    );

    expect(screen.getByTestId("subnet-field")).toBeInTheDocument();
    expect(
      screen.queryByTestId("prefixed-ip-address-field")
    ).not.toBeInTheDocument();
  });

  it("shows the prefixed IP address field when a subnet is selected", () => {
    interfaces[0].ip_assignment = DeviceIpAssignment.STATIC;
    interfaces[0].subnet = state.subnet.items[0].id.toString();

    renderWithProviders(
      <Formik initialValues={{ interfaces }} onSubmit={vi.fn()}>
        <AddDeviceInterfaces />
      </Formik>,
      { state }
    );

    expect(screen.getByTestId("prefixed-ip-address-field")).toBeInTheDocument();
    expect(screen.queryByTestId("ip-address-field")).not.toBeInTheDocument();
  });

  it("can add and remove interfaces", async () => {
    renderWithProviders(
      <Formik initialValues={{ interfaces }} onSubmit={vi.fn()}>
        <AddDeviceInterfaces />
      </Formik>,
      { state }
    );

    const getCardCount = () => screen.getAllByTestId("interface-card").length;

    // There is only one interface by default. Since at least one interface must
    // be defined, the remove button should be hidden.
    expect(getCardCount()).toBe(1);
    expect(
      screen.queryByRole("button", { name: /delete/i })
    ).not.toBeInTheDocument();

    // Add an interface.
    await userEvent.click(
      screen.getByRole("button", { name: /Add interface/i })
    );

    expect(getCardCount()).toBe(2);
    expect(screen.queryAllByRole("button", { name: /delete/i })).toHaveLength(
      2
    );

    // Remove an interface.
    await userEvent.click(
      within(screen.getAllByTestId("interface-card")[0]).getByRole("button", {
        name: /delete/i,
      })
    );

    expect(getCardCount()).toBe(1);
    expect(
      screen.queryByRole("button", { name: /delete/i })
    ).not.toBeInTheDocument();
  });
});
