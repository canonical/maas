import AddBridgeForm from "./AddBridgeForm";

import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { NetworkInterface } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  within,
  renderWithProviders,
} from "@/testing/utils";

describe("AddBridgeForm", () => {
  let nic: NetworkInterface;
  let state: RootState;
  const fabric = factory.fabric();
  beforeEach(() => {
    nic = factory.machineInterface({
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    state = factory.rootState({
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
      fabric: factory.fabricState({
        items: [fabric, factory.fabric()],
        loaded: true,
      }),
      vlan: factory.vlanState({
        items: [
          factory.vlan({
            id: 39,
            fabric: fabric.id,
            vid: 2,
            name: "vlan-name",
            external_dhcp: null,
            dhcp_on: true,
          }),
        ],
        loaded: true,
      }),
    });
  });

  it("displays a table", () => {
    const nic = factory.machineInterface({
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        interfaces: [nic],
      }),
    ];
    const selected = [{ nicId: nic.id }];
    renderWithProviders(
      <AddBridgeForm
        selected={selected}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );
    const table = screen.getByRole("grid");
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    expect(within(table).getByText("eth2")).toBeInTheDocument();
  });

  it("fetches the necessary data on load", () => {
    const { store } = renderWithProviders(
      <AddBridgeForm
        selected={[{ nicId: nic.id }]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );
    expect(store.getActions().some((action) => action.type === "vlan/fetch"));
  });

  it("displays a spinner when data is loading", () => {
    state.vlan.loaded = false;
    state.machine.loaded = false;
    renderWithProviders(
      <AddBridgeForm
        selected={[{ nicId: nic.id }]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );

    // Multiple spinners are displayed, so we have to check that there is at least one
    expect(screen.getAllByText("Loading").length).toBeGreaterThanOrEqual(1);
  });

  it("can dispatch an action to add a bridge", async () => {
    state.machine.selected = { items: ["abc123", "def456"] };
    const { store } = renderWithProviders(
      <AddBridgeForm
        selected={[{ nicId: nic.id }]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );

    const macAddressField = screen.getByRole("textbox", {
      name: "MAC address",
    });

    await userEvent.clear(macAddressField);
    await userEvent.type(macAddressField, "28:21:c6:b9:1b:22");

    await userEvent.click(
      screen.getByRole("button", { name: "Save interface" })
    );

    expect(
      store
        .getActions()
        .find((action) => action.type === "machine/createBridge")
    ).toStrictEqual({
      type: "machine/createBridge",
      meta: {
        model: "machine",
        method: "create_bridge",
      },
      payload: {
        params: {
          bridge_stp: false,
          fabric: "1",
          bridge_type: "standard",
          mac_address: "28:21:c6:b9:1b:22",
          name: "br0",
          parents: [nic.id],
          system_id: "abc123",
          tags: [],
          vlan: "39",
        },
      },
    });
  });

  it("can dispatch an action to add a bridge with multiple interfaces", async () => {
    const nic1 = factory.machineInterface({
      type: NetworkInterfaceTypes.PHYSICAL,
      name: "eth0",
    });
    const nic2 = factory.machineInterface({
      type: NetworkInterfaceTypes.PHYSICAL,
      name: "eth1",
    });

    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        interfaces: [nic1, nic2],
      }),
    ];

    const { store } = renderWithProviders(
      <AddBridgeForm
        selected={[{ nicId: nic1.id }, { nicId: nic2.id }]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );

    // Ensure both interfaces are shown in the table
    const table = screen.getByRole("grid");
    const rows = within(within(table).getAllByRole("rowgroup")[1]).getAllByRole(
      "row"
    );
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("eth0")).toBeInTheDocument();
    expect(within(rows[1]).getByText("eth1")).toBeInTheDocument();

    const macAddressField = screen.getByRole("textbox", {
      name: "MAC address",
    });

    await userEvent.clear(macAddressField);
    await userEvent.type(macAddressField, "28:21:c6:b9:1b:22");

    await userEvent.click(
      screen.getByRole("button", { name: "Save interface" })
    );

    expect(
      store
        .getActions()
        .find((action) => action.type === "machine/createBridge")
    ).toStrictEqual({
      type: "machine/createBridge",
      meta: {
        model: "machine",
        method: "create_bridge",
      },
      payload: {
        params: {
          bridge_stp: false,
          fabric: "1",
          bridge_type: "standard",
          mac_address: "28:21:c6:b9:1b:22",
          name: "br0",
          parents: [nic1.id, nic2.id],
          system_id: "abc123",
          tags: [],
          vlan: "39",
        },
      },
    });
  });
});
