import ReserveDHCPLease from "./ReserveDHCPLease";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  getTestState,
  renderWithProviders,
  userEvent,
  screen,
  mockSidePanel,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

const { getComputedStyle } = window;
let state: RootState;

describe("ReserveDHCPLease", () => {
  beforeAll(() => {
    // getComputedStyle is not implemeneted in jsdom, so we need to do this.
    window.getComputedStyle = (elt) => getComputedStyle(elt);
  });

  beforeEach(() => {
    state = getTestState();
    state.subnet = factory.subnetState({
      loading: false,
      loaded: true,
      items: [factory.subnet({ id: 1, cidr: "10.0.0.0/24" })],
    });
  });

  afterAll(() => {
    // Reset to original implementation
    window.getComputedStyle = getComputedStyle;
  });

  it("displays an error if an invalid IP address is entered", async () => {
    renderWithProviders(
      <ReserveDHCPLease subnetId={state.subnet.items[0].id} />,
      { state }
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "IP address" }),
      "420"
    );
    await userEvent.tab();

    expect(
      screen.getByText("This is not a valid IP address")
    ).toBeInTheDocument();
  });

  it("displays an error if an out-of-range IP address is entered", async () => {
    state.subnet.items = [factory.subnet({ id: 1, cidr: "10.0.0.0/25" })];
    renderWithProviders(
      <ReserveDHCPLease subnetId={state.subnet.items[0].id} />,
      { state }
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "IP address" }),
      "129"
    );
    await userEvent.tab();

    expect(
      screen.getByText("The IP address is outside of the subnet's range.")
    ).toBeInTheDocument();
  });

  it("displays an error if the IP address or the MAC address are not entered", async () => {
    state.subnet.items = [factory.subnet({ id: 1, cidr: "10.0.0.0/25" })];
    renderWithProviders(
      <ReserveDHCPLease subnetId={state.subnet.items[0].id} />,
      { state }
    );

    await userEvent.click(screen.getByRole("textbox", { name: "IP address" }));
    await userEvent.click(screen.getByRole("textbox", { name: "MAC address" }));
    await userEvent.tab();

    expect(screen.getByText("IP address is required")).toBeInTheDocument();
    expect(screen.getByText("MAC address is required")).toBeInTheDocument();
  });

  it("closes the side panel when the cancel button is clicked", async () => {
    renderWithProviders(
      <ReserveDHCPLease subnetId={state.subnet.items[0].id} />,
      { state }
    );

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(mockClose).toHaveBeenCalled();
  });

  it("dispatches an action to create a reserved IP", async () => {
    const { store } = renderWithProviders(
      <ReserveDHCPLease subnetId={state.subnet.items[0].id} />,
      { state }
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "IP address" }),
      "69"
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "MAC address" }),
      "FF:FF:FF:FF:FF:FF"
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "Comment" }),
      "bla bla bla"
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Reserve static DHCP lease" })
    );

    expect(
      store.getActions().find((action) => action.type === "reservedip/create")
    ).toEqual({
      meta: {
        method: "create",
        model: "reservedip",
      },
      payload: {
        params: {
          subnet: 1,
          ip: "10.0.0.69",
          mac_address: "FF:FF:FF:FF:FF:FF",
          comment: "bla bla bla",
        },
      },
      type: "reservedip/create",
    });
  });

  it("pre-fills the form if a reserved IP's ID is present", async () => {
    const reservedIp = factory.reservedIp({
      id: 1,
      ip: "10.0.0.2",
      mac_address: "FF:FF:FF:FF:FF:FF",
      comment: "bla bla bla",
    });
    state.reservedip = factory.reservedIpState({
      loading: false,
      loaded: true,
      items: [reservedIp],
    });

    renderWithProviders(
      <ReserveDHCPLease
        reservedIpId={reservedIp.id}
        subnetId={state.subnet.items[0].id}
      />,
      { state }
    );

    expect(screen.getByRole("textbox", { name: "IP address" })).toHaveValue(
      "2"
    );
    expect(screen.getByRole("textbox", { name: "MAC address" })).toHaveValue(
      reservedIp.mac_address
    );
    expect(screen.getByRole("textbox", { name: "Comment" })).toHaveValue(
      reservedIp.comment
    );
  });

  it("pre-fills the form if a reserved IPv6 address's ID is present", async () => {
    const reservedIp = factory.reservedIp({
      id: 1,
      ip: "2001:db8::2",
      mac_address: "FF:FF:FF:FF:FF:FF",
      comment: "bla bla bla",
    });
    state.reservedip = factory.reservedIpState({
      loading: false,
      loaded: true,
      items: [reservedIp],
    });
    state.subnet.items = [factory.subnet({ id: 1, cidr: "2001:db8::/64" })];

    renderWithProviders(
      <ReserveDHCPLease
        reservedIpId={reservedIp.id}
        subnetId={state.subnet.items[0].id}
      />,
      { state }
    );

    expect(screen.getByRole("textbox", { name: "IP address" })).toHaveValue(
      ":2"
    );
    expect(screen.getByRole("textbox", { name: "MAC address" })).toHaveValue(
      reservedIp.mac_address
    );
    expect(screen.getByRole("textbox", { name: "Comment" })).toHaveValue(
      reservedIp.comment
    );
  });

  it("disables the IP address and MAC address fields when editing a lease", async () => {
    const reservedIp = factory.reservedIp({
      id: 1,
      ip: "10.0.0.69",
      mac_address: "FF:FF:FF:FF:FF:FF",
      comment: "bla bla bla",
    });
    state.reservedip = factory.reservedIpState({
      loading: false,
      loaded: true,
      items: [reservedIp],
    });

    renderWithProviders(
      <ReserveDHCPLease
        reservedIpId={reservedIp.id}
        subnetId={state.subnet.items[0].id}
      />,
      { state }
    );

    expect(screen.getByRole("textbox", { name: "IP address" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "MAC address" })).toBeDisabled();
  });

  it("dispatches an action to update a reserved IP", async () => {
    const reservedIp = factory.reservedIp({
      id: 1,
      ip: "10.0.0.69",
      mac_address: "FF:FF:FF:FF:FF:FF",
      comment: "bla bla bla",
    });
    state.reservedip = factory.reservedIpState({
      loading: false,
      loaded: true,
      items: [reservedIp],
    });

    const { store } = renderWithProviders(
      <ReserveDHCPLease
        reservedIpId={reservedIp.id}
        subnetId={state.subnet.items[0].id}
      />,
      { state }
    );

    await userEvent.clear(screen.getByRole("textbox", { name: "Comment" }));

    await userEvent.type(
      screen.getByRole("textbox", { name: "Comment" }),
      "something imaginative and funny"
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Update static DHCP lease" })
    );

    expect(
      store.getActions().find((action) => action.type === "reservedip/update")
    ).toEqual({
      meta: {
        method: "update",
        model: "reservedip",
      },
      payload: {
        params: {
          subnet: 1,
          id: reservedIp.id,
          mac_address: "FF:FF:FF:FF:FF:FF",
          comment: "something imaginative and funny",
        },
      },
      type: "reservedip/update",
    });
  });

  it("displays an error if an invalid IPv6 address is entered", async () => {
    state.subnet.items = [factory.subnet({ id: 1, cidr: "2001:db8::/64" })];
    renderWithProviders(
      <ReserveDHCPLease subnetId={state.subnet.items[0].id} />,
      { state }
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "IP address" }),
      "420"
    );
    await userEvent.tab();

    expect(
      screen.getByText("This is not a valid IP address")
    ).toBeInTheDocument();
  });

  it("dispatches an action to create a reserved IPv6 address", async () => {
    state.subnet.items = [factory.subnet({ id: 1, cidr: "2001:db8::/64" })];

    const { store } = renderWithProviders(
      <ReserveDHCPLease subnetId={state.subnet.items[0].id} />,
      { state }
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "IP address" }),
      ":69"
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "MAC address" }),
      "FF:FF:FF:FF:FF:FF"
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "Comment" }),
      "bla bla bla"
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Reserve static DHCP lease" })
    );

    expect(
      store.getActions().find((action) => action.type === "reservedip/create")
    ).toEqual({
      meta: {
        method: "create",
        model: "reservedip",
      },
      payload: {
        params: {
          subnet: 1,
          ip: "2001:db8::69",
          mac_address: "FF:FF:FF:FF:FF:FF",
          comment: "bla bla bla",
        },
      },
      type: "reservedip/create",
    });
  });
});
