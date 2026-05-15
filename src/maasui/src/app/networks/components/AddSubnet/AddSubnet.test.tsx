import AddSubnet from "./AddSubnet";

import { subnetActions } from "@/app/store/subnet";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  mockSidePanel,
  renderWithProviders,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("AddSubnet", () => {
  const vlan1 = factory.vlan({ id: 111, fabric: 5 });
  const vlan2 = factory.vlan({
    id: 222,
    vid: 333,
    name: "",
    fabric: 5,
  });
  const fabric = factory.fabric({
    id: 5,
    name: "space1",
    vlan_ids: [vlan1.id, vlan2.vid],
    default_vlan_id: vlan1.id,
  });

  const state = factory.rootState({
    fabric: factory.fabricState({
      loaded: true,
      items: [fabric],
    }),
    vlan: factory.vlanState({
      loaded: true,
      items: [vlan1, vlan2],
    }),
  });

  it("runs closeSidePanel function when the cancel button is clicked", async () => {
    renderWithProviders(<AddSubnet />);

    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls create subnet on save click", async () => {
    const { store } = renderWithProviders(<AddSubnet />, { state });

    const cidr = "192.168.0.1";
    const name = "Subnet name";

    await userEvent.type(screen.getByRole("textbox", { name: /CIDR/ }), cidr);
    await userEvent.type(screen.getByRole("textbox", { name: /Name/ }), name);

    await waitFor(() => {
      expect(
        screen.getByRole("combobox", { name: "VLAN" })
      ).toBeInTheDocument();
    });
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Fabric" }),
      fabric.name
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "VLAN" }),
      `${vlan2.vid}`
    );

    await userEvent.click(screen.getByRole("button", { name: /Save subnet/i }));

    await waitFor(() => {
      expect(store.getActions()).toStrictEqual([
        subnetActions.cleanup(),
        subnetActions.create({
          cidr,
          fabric: fabric.id,
          name,
          dns_servers: "",
          gateway_ip: "",
          vlan: vlan2.id,
        }),
      ]);
    });
  });

  it("displays error message when create subnet fails", async () => {
    const errorState = factory.rootState({
      ...state,
      subnet: factory.subnetState({ errors: "Uh oh!" }),
    });

    renderWithProviders(<AddSubnet />, { state: errorState });

    const cidr = "192.168.0.1";
    const name = "Subnet name";

    await userEvent.type(screen.getByRole("textbox", { name: /CIDR/ }), cidr);
    await userEvent.type(screen.getByRole("textbox", { name: /Name/ }), name);

    await waitFor(() => {
      expect(
        screen.getByRole("combobox", { name: "VLAN" })
      ).toBeInTheDocument();
    });
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Fabric" }),
      fabric.name
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "VLAN" }),
      `${vlan2.vid}`
    );

    await userEvent.click(screen.getByRole("button", { name: /Save subnet/i }));

    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
