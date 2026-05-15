import { Formik } from "formik";

import type { ConfigureDHCPValues } from "../ConfigureDHCP";
import { DHCPType } from "../ConfigureDHCP";

import DHCPReservedRanges, { Headers } from "./DHCPReservedRanges";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import {
  mockIsPending,
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

let initialValues: ConfigureDHCPValues;

beforeEach(() => {
  initialValues = {
    dhcpType: DHCPType.CONTROLLERS,
    enableDHCP: true,
    endIP: "",
    gatewayIP: "",
    primaryRack: "",
    relayVLAN: "",
    secondaryRack: "",
    startIP: "",
    subnet: "",
  };
});

describe("DHCPReservedRanges", () => {
  describe("display", () => {
    it("does not render when DHCP is disabled", () => {
      const vlan = factory.vlan();
      const state = factory.rootState({
        iprange: factory.ipRangeState({ items: [] }),
        subnet: factory.subnetState({ items: [] }),
        vlan: factory.vlanState({ items: [vlan] }),
      });

      renderWithProviders(
        <Formik
          initialValues={{ ...initialValues, enableDHCP: false }}
          onSubmit={vi.fn()}
        >
          <DHCPReservedRanges id={vlan.id} />
        </Formik>,
        { state }
      );

      expect(
        screen.queryByText("Reserved dynamic range")
      ).not.toBeInTheDocument();
    });

    it("displays a loading component when data is loading", async () => {
      mockIsPending();
      const vlan = factory.vlan();
      const state = factory.rootState({
        iprange: factory.ipRangeState({
          items: [factory.ipRange({ vlan: vlan.id })],
          loading: true,
        }),
        subnet: factory.subnetState({ items: [] }),
        vlan: factory.vlanState({ items: [vlan] }),
      });

      renderWithProviders(
        <Formik initialValues={initialValues} onSubmit={vi.fn()}>
          <DHCPReservedRanges id={vlan.id} />
        </Formik>,
        { state }
      );

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list with no ranges", async () => {
      const vlan = factory.vlan();
      const state = factory.rootState({
        iprange: factory.ipRangeState({ items: [] }),
        subnet: factory.subnetState({ items: [], loaded: true }),
        vlan: factory.vlanState({ items: [vlan] }),
      });

      renderWithProviders(
        <Formik initialValues={initialValues} onSubmit={vi.fn()}>
          <DHCPReservedRanges id={vlan.id} />
        </Formik>,
        { state }
      );

      expect(screen.getByText("Reserved dynamic range")).toBeInTheDocument();
      expect(
        screen.getByRole("combobox", { name: "Subnet" })
      ).toBeInTheDocument();
    });

    it("displays the columns correctly for existing IP ranges", () => {
      const vlan = factory.vlan();
      const subnet = factory.subnet({
        gateway_ip: "192.168.1.11",
        vlan: vlan.id,
      });
      const ipRange = factory.ipRange({
        start_ip: "192.168.1.1",
        end_ip: "192.168.1.10",
        subnet: subnet.id,
        vlan: vlan.id,
      });
      const state = factory.rootState({
        iprange: factory.ipRangeState({ items: [ipRange] }),
        subnet: factory.subnetState({ items: [subnet] }),
        vlan: factory.vlanState({ items: [vlan] }),
      });

      renderWithProviders(
        <Formik initialValues={initialValues} onSubmit={vi.fn()}>
          <DHCPReservedRanges id={vlan.id} />
        </Formik>,
        { state }
      );

      [
        "Subnet",
        Headers.StartIP,
        Headers.EndIP,
        Headers.GatewayIP,
        Headers.Comment,
      ].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });

    it("displays the columns correctly for form mode (no existing ranges)", () => {
      const vlan = factory.vlan();
      const subnet = factory.subnet({ vlan: vlan.id });
      const state = factory.rootState({
        iprange: factory.ipRangeState({ items: [] }),
        subnet: factory.subnetState({ items: [subnet], loaded: true }),
        vlan: factory.vlanState({ items: [vlan] }),
      });

      renderWithProviders(
        <Formik initialValues={initialValues} onSubmit={vi.fn()}>
          <DHCPReservedRanges id={vlan.id} />
        </Formik>,
        { state }
      );

      ["Subnet", Headers.StartIP, Headers.EndIP, Headers.GatewayIP].forEach(
        (column) => {
          expect(
            screen.getByRole("columnheader", {
              name: new RegExp(`^${column}`, "i"),
            })
          ).toBeInTheDocument();
        }
      );

      expect(
        screen.queryByRole("columnheader", {
          name: new RegExp(`^${Headers.Comment}`, "i"),
        })
      ).not.toBeInTheDocument();
    });

    it("renders a table of IP ranges if the VLAN has any defined", () => {
      const vlan = factory.vlan();
      const subnet = factory.subnet({
        gateway_ip: "192.168.1.11",
        vlan: vlan.id,
      });
      const ipRange = factory.ipRange({
        start_ip: "192.168.1.1",
        end_ip: "192.168.1.10",
        subnet: subnet.id,
        vlan: vlan.id,
      });
      const state = factory.rootState({
        iprange: factory.ipRangeState({ items: [ipRange] }),
        subnet: factory.subnetState({ items: [subnet] }),
        vlan: factory.vlanState({ items: [vlan] }),
      });

      renderWithProviders(
        <Formik initialValues={initialValues} onSubmit={vi.fn()}>
          <DHCPReservedRanges id={vlan.id} />
        </Formik>,
        { state }
      );

      const subnetCell = screen.getByRole("cell", {
        name: new RegExp(subnet.name),
      });
      expect(within(subnetCell).getByRole("link")).toHaveAttribute(
        "href",
        urls.networks.subnet.index({ id: subnet.id })
      );

      expect(
        screen.getByRole("cell", { name: ipRange.start_ip })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("cell", { name: ipRange.end_ip })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("cell", { name: `${subnet.gateway_ip}` })
      ).toBeInTheDocument();
    });

    it("renders only a subnet select field if no IP ranges exist and no subnet is selected", () => {
      const vlan = factory.vlan();
      const subnet = factory.subnet({
        gateway_ip: "192.168.1.11",
        vlan: vlan.id,
      });
      const state = factory.rootState({
        iprange: factory.ipRangeState({ items: [] }),
        subnet: factory.subnetState({ items: [subnet], loaded: true }),
        vlan: factory.vlanState({ items: [vlan] }),
      });

      renderWithProviders(
        <Formik initialValues={initialValues} onSubmit={vi.fn()}>
          <DHCPReservedRanges id={vlan.id} />
        </Formik>,
        { state }
      );

      expect(
        within(screen.getByRole("cell", { name: /Select subnet/i })).getByRole(
          "combobox",
          { name: "Subnet" }
        )
      ).toBeInTheDocument();

      // all the other cells should be empty
      expect(screen.getAllByRole("cell", { name: "" })).toHaveLength(3);
    });

    it("renders a subnet select field and prepopulated fields for a reserved range if no IP ranges exist and a subnet is selected", async () => {
      const vlan = factory.vlan();
      const subnet = factory.subnet({
        gateway_ip: "192.168.1.11",
        statistics: factory.subnetStatistics({
          suggested_dynamic_range: factory.subnetStatisticsRange({
            start: "192.168.1.1",
            end: "192.168.1.5",
          }),
        }),
        vlan: vlan.id,
      });
      const state = factory.rootState({
        iprange: factory.ipRangeState({ items: [] }),
        subnet: factory.subnetState({ items: [subnet], loaded: true }),
        vlan: factory.vlanState({ items: [vlan] }),
      });

      renderWithProviders(
        <Formik initialValues={initialValues} onSubmit={vi.fn()}>
          <DHCPReservedRanges id={vlan.id} />
        </Formik>,
        { state }
      );

      await userEvent.selectOptions(
        screen.getByRole("combobox", { name: "Subnet" }),
        subnet.id.toString()
      );

      expect(
        screen.getByRole("textbox", { name: Headers.StartIP })
      ).toHaveAttribute(
        "value",
        subnet.statistics.suggested_dynamic_range.start
      );
      expect(
        screen.getByRole("textbox", { name: Headers.EndIP })
      ).toHaveAttribute("value", subnet.statistics.suggested_dynamic_range.end);
      expect(
        screen.getByRole("textbox", { name: Headers.GatewayIP })
      ).toHaveAttribute("value", subnet.gateway_ip);
    });
  });
});
