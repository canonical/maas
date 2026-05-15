import userEvent from "@testing-library/user-event";

import EditBridgeForm from "./EditBridgeForm";

import type { RootState } from "@/app/store/root/types";
import {
  BridgeType,
  NetworkInterfaceTypes,
  NetworkLinkMode,
} from "@/app/store/types/enum";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("EditBridgeForm", () => {
  let nic: NetworkInterface;
  let link: NetworkLink;
  let state: RootState;
  beforeEach(() => {
    link = factory.networkLink({});
    nic = factory.machineInterface({
      links: [link],
      params: {
        bridge_type: BridgeType.OVS,
      },
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    state = factory.rootState({
      vlan: factory.vlanState({
        loaded: true,
        loading: false,
        items: [factory.vlan({ id: 1, fabric: 1 })],
      }),
      subnet: factory.subnetState({
        loaded: true,
        loading: false,
        items: [factory.subnet({ id: 1, vlan: 1 })],
      }),
      fabric: factory.fabricState({
        loaded: true,
        loading: false,
        items: [factory.fabric({ id: 1 })],
      }),
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            interfaces: [nic],
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
  });

  it("fetches the necessary data on load", async () => {
    const { store } = renderWithProviders(
      <EditBridgeForm link={link} nic={nic} systemId="abc123" />,
      { state }
    );
    expect(
      store.getActions().some((action) => action.type === "vlan/fetch")
    ).toBe(true);
  });

  it("displays a spinner when data is loading", () => {
    state.vlan.loaded = false;
    state.vlan.loading = true;
    renderWithProviders(
      <EditBridgeForm link={link} nic={nic} systemId="abc123" />,
      { state }
    );
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("can dispatch an action to update a bridge", async () => {
    state.machine.selected = { items: ["abc123", "def456"] };
    const { store } = renderWithProviders(
      <EditBridgeForm link={link} nic={nic} systemId="abc123" />,
      { state }
    );

    await userEvent.clear(screen.getByRole("textbox", { name: "Bridge name" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "Bridge name" }),
      "br1"
    );

    await userEvent.clear(screen.getByRole("textbox", { name: "MAC address" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "MAC address" }),
      "28:21:c6:b9:1b:22"
    );

    await userEvent.type(screen.getByRole("textbox", { name: "Tags" }), "a");
    await userEvent.click(screen.getByTestId("new-tag"));
    await userEvent.type(screen.getByRole("textbox", { name: "Tags" }), "tag");
    await userEvent.click(screen.getByTestId("new-tag"));

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Fabric" }),
      "1"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "VLAN" }),
      "1"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Subnet" }),
      "1"
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Save Physical" })
    );

    expect(
      store
        .getActions()
        .find((action) => action.type === "machine/updateInterface")
    ).toStrictEqual({
      type: "machine/updateInterface",
      meta: {
        model: "machine",
        method: "update_interface",
      },
      payload: {
        params: {
          bridge_stp: false,
          bridge_type: BridgeType.OVS,
          fabric: "1",
          interface_id: nic.id,
          link_id: link.id,
          mac_address: "28:21:c6:b9:1b:22",
          mode: NetworkLinkMode.LINK_UP,
          name: "br1",
          subnet: "1",
          system_id: "abc123",
          tags: ["a", "tag"],
          vlan: "1",
        },
      },
    });
  });
});
