import EditPhysicalForm from "./EditPhysicalForm";

import type { RootState } from "@/app/store/root/types";
import { NetworkLinkMode } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("EditPhysicalForm", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      fabric: factory.fabricState({
        items: [factory.fabric({ id: 1 }), factory.fabric()],
        loaded: true,
      }),
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            interfaces: [
              factory.machineInterface({
                id: 1,
                vlan_id: 1,
                links: [factory.networkLink({ id: 1, subnet_id: 1 })],
              }),
            ],
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
      subnet: factory.subnetState({
        items: [
          factory.subnet({
            id: 1,
            vlan: 1,
            cidr: "10.0.0.0/24",
            statistics: factory.subnetStatistics({ ip_version: 4 }),
          }),
        ],
        loaded: true,
      }),
      vlan: factory.vlanState({
        items: [factory.vlan({ id: 1, fabric: 1 }), factory.vlan()],
        loaded: true,
      }),
    });
  });

  it("fetches the necessary data on load", () => {
    const { store } = renderWithProviders(
      <EditPhysicalForm nicId={1} systemId="abc123" />,
      {
        state,
      }
    );
    const expectedActions = ["fabric/fetch", "vlan/fetch"];
    expectedActions.forEach((expectedAction) => {
      expect(
        store.getActions().some((action) => action.type === expectedAction)
      );
    });
  });

  it("displays a spinner when data is loading", () => {
    state.vlan.loaded = false;
    state.fabric.loaded = false;
    renderWithProviders(<EditPhysicalForm nicId={1} systemId="abc123" />, {
      state,
    });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("displays an error if an IP address is not valid", async () => {
    renderWithProviders(<EditPhysicalForm nicId={1} systemId="abc123" />, {
      state,
    });

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Subnet" }),
      state.subnet.items[0].id.toString()
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "IP assignment" }),
      "Static (Client configured)"
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "IP address" }),
      "abc"
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Save interface" })
    );

    expect(
      screen.getByText("This is not a valid IP address")
    ).toBeInTheDocument();
  });

  it("displays an error if an IP address is out of range", async () => {
    renderWithProviders(<EditPhysicalForm nicId={1} systemId="abc123" />, {
      state,
    });

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Subnet" }),
      state.subnet.items[0].id.toString()
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "IP assignment" }),
      "Static (Client configured)"
    );

    await userEvent.clear(screen.getByRole("textbox", { name: "IP address" }));

    await userEvent.type(
      screen.getByRole("textbox", { name: "IP address" }),
      "255"
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Save interface" })
    );

    expect(
      screen.getByText("The IP address is outside of the subnet's range.")
    ).toBeInTheDocument();
  });

  it("correctly dispatches actions to edit a physical interface", async () => {
    const { store } = renderWithProviders(
      <EditPhysicalForm linkId={1} nicId={1} systemId="abc123" />,
      { state }
    );

    await userEvent.clear(screen.getByRole("textbox", { name: "Name" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "eth1");

    await userEvent.clear(screen.getByRole("textbox", { name: "MAC address" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "MAC address" }),
      "28:21:c6:b9:1b:22"
    );

    await userEvent.clear(
      screen.getByRole("textbox", { name: "Interface speed (Gbps)" })
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Interface speed (Gbps)" }),
      "1.5"
    );

    await userEvent.clear(
      screen.getByRole("textbox", { name: "Link speed (Gbps)" })
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Link speed (Gbps)" }),
      "1"
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Fabric" }),
      "1"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "VLAN" }),
      "1"
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Save interface" })
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
          fabric: "1",
          interface_id: 1,
          interface_speed: 1500,
          link_id: 1,
          link_speed: 1000,
          mac_address: "28:21:c6:b9:1b:22",
          mode: NetworkLinkMode.LINK_UP,
          name: "eth1",
          system_id: "abc123",
          tags: [],
          vlan: "1",
        },
      },
    });
  });
});
