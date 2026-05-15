import AddBondForm from "./AddBondForm";

import { BondMode } from "@/app/store/general/types";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  within,
  renderWithProviders,
} from "@/testing/utils";

describe("AddBondForm", () => {
  let state: RootState;
  const fabric = factory.fabric();
  beforeEach(() => {
    state = factory.rootState({
      fabric: factory.fabricState({
        loaded: true,
        items: [fabric],
      }),
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
      subnet: factory.subnetState({
        loaded: true,
        items: [factory.subnet()],
      }),
      vlan: factory.vlanState({
        items: [
          factory.vlan({
            fabric: fabric.id,
            id: 1,
          }),
        ],
        loaded: true,
      }),
    });
  });

  it("displays a table", () => {
    state.machine.items = [
      factory.machineDetails({
        interfaces: [
          factory.machineInterface({
            id: 9,
            type: NetworkInterfaceTypes.PHYSICAL,
            vlan_id: 1,
          }),
          factory.machineInterface({
            id: 10,
            type: NetworkInterfaceTypes.PHYSICAL,
            vlan_id: 1,
          }),
        ],
        system_id: "abc123",
      }),
    ];
    renderWithProviders(
      <AddBondForm
        selected={[{ nicId: 9 }, { nicId: 10 }]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );
    expect(
      screen.getByRole("form", { name: "Create bond" })
    ).toBeInTheDocument();
    expect(screen.getByRole("grid")).toBeInTheDocument();
  });

  it("displays the selected interfaces when not editing members", async () => {
    const interfaces = [
      factory.machineInterface({
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
        name: "test-interface-1",
      }),
      factory.machineInterface({
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
        name: "test-interface-2",
      }),
    ];
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        interfaces,
      }),
    ];
    const selected = [{ nicId: interfaces[0].id }, { nicId: interfaces[1].id }];
    renderWithProviders(
      <AddBondForm
        selected={selected}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );
    const table = screen.getByRole("grid");
    expect(within(table).getByText("test-interface-1")).toBeInTheDocument();
    expect(within(table).getByText("test-interface-2")).toBeInTheDocument();
  });

  it("displays all valid interfaces when editing members", async () => {
    const interfaces = [
      factory.machineInterface({
        name: "test-interface-1",
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
      }),
      factory.machineInterface({
        name: "test-interface-2",
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
      }),
      // VLANs are not valid.
      factory.machineInterface({
        name: "test-interface-3",
        type: NetworkInterfaceTypes.VLAN,
        vlan_id: 1,
      }),
      // Bridges are not valid.
      factory.machineInterface({
        name: "test-interface-4",
        type: NetworkInterfaceTypes.BRIDGE,
        vlan_id: 1,
      }),
      // Bonds are not valid.
      factory.machineInterface({
        name: "test-interface-5",
        type: NetworkInterfaceTypes.BOND,
        vlan_id: 1,
      }),
      // Physical interfaces in other VLANs are not valid.
      factory.machineInterface({
        name: "test-interface-6",
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 2,
      }),
      // Physical interfaces in the same VLAN are valid.
      factory.machineInterface({
        name: "test-interface-7",
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
      }),
    ];
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        interfaces,
      }),
    ];
    const selected = [{ nicId: interfaces[0].id }, { nicId: interfaces[1].id }];
    renderWithProviders(
      <AddBondForm
        selected={selected}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );
    let table = screen.getByRole("grid");
    // Check that selected interfaces are shown
    expect(within(table).getByText("test-interface-1")).toBeInTheDocument();
    expect(within(table).getByText("test-interface-2")).toBeInTheDocument();

    // Check that unselected interfaces are not shown
    expect(
      within(table).queryByText("test-interface-3")
    ).not.toBeInTheDocument();
    expect(
      within(table).queryByText("test-interface-4")
    ).not.toBeInTheDocument();
    expect(
      within(table).queryByText("test-interface-5")
    ).not.toBeInTheDocument();
    expect(
      within(table).queryByText("test-interface-6")
    ).not.toBeInTheDocument();
    expect(
      within(table).queryByText("test-interface-7")
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByTestId("edit-members"));
    table = screen.getByRole("grid");

    // Check that only valid interfaces are shown
    expect(within(table).getByText("test-interface-1")).toBeInTheDocument();
    expect(within(table).getByText("test-interface-2")).toBeInTheDocument();
    expect(within(table).getByText("test-interface-7")).toBeInTheDocument();

    // Ensure invalid interfaces are not shown
    expect(
      within(table).queryByText("test-interface-3")
    ).not.toBeInTheDocument();
    expect(
      within(table).queryByText("test-interface-4")
    ).not.toBeInTheDocument();
    expect(
      within(table).queryByText("test-interface-5")
    ).not.toBeInTheDocument();
    expect(
      within(table).queryByText("test-interface-6")
    ).not.toBeInTheDocument();
  });

  // TODO: rerender does not work with redux state, add back in v3
  it.skip("disables the submit button if two interfaces aren't selected", async () => {
    const interfaces = [
      factory.machineInterface({
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
      }),
      factory.machineInterface({
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
      }),
      factory.machineInterface({
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
      }),
    ];
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        interfaces,
      }),
    ];
    const { rerender } = renderWithProviders(
      <AddBondForm
        selected={[{ nicId: interfaces[0].id }, { nicId: interfaces[1].id }]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      {
        state,
      }
    );
    await userEvent.click(screen.getByTestId("edit-members"));

    rerender(
      <AddBondForm selected={[]} setSelected={vi.fn()} systemId="abc123" />
    );
    expect(
      screen.getByRole("button", { name: "Save interface" })
    ).toBeDisabled();
  });

  it("fetches the necessary data on load", async () => {
    const { store } = renderWithProviders(
      <AddBondForm selected={[]} setSelected={vi.fn()} systemId="abc123" />,
      { state }
    );
    expect(store.getActions().some((action) => action.type === "fabric/fetch"));
    expect(store.getActions().some((action) => action.type === "subnet/fetch"));
    expect(store.getActions().some((action) => action.type === "vlan/fetch"));
  });

  it("displays a spinner when data is loading", async () => {
    state.fabric.loaded = false;
    state.subnet.loaded = false;
    state.vlan.loaded = false;
    renderWithProviders(
      <AddBondForm selected={[]} setSelected={vi.fn()} systemId="abc123" />,
      { state }
    );
    expect(screen.getByText("Loading")).toBeInTheDocument();
  });

  it("displays a spinner if the VLAN hasn't been set", async () => {
    state.fabric.loaded = true;
    state.subnet.loaded = true;
    state.vlan.loaded = true;
    renderWithProviders(
      <AddBondForm selected={[]} setSelected={vi.fn()} systemId="abc123" />,
      { state }
    );
    expect(screen.getByTestId("data-loading")).toBeInTheDocument();
  });

  it("can dispatch an action to add a bond", async () => {
    state.machine.items = [
      factory.machineDetails({
        interfaces: [
          factory.machineInterface({
            id: 9,
            type: NetworkInterfaceTypes.PHYSICAL,
            vlan_id: 1,
            mac_address: "00:00:00:00:00:15",
          }),
          factory.machineInterface({
            id: 10,
            type: NetworkInterfaceTypes.PHYSICAL,
            vlan_id: 1,
          }),
        ],
        system_id: "abc123",
      }),
    ];
    const { store } = renderWithProviders(
      <AddBondForm
        selected={[{ nicId: 9 }, { nicId: 10 }]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Save interface" })
    );
    expect(
      store.getActions().find((action) => action.type === "machine/createBond")
    ).toStrictEqual({
      type: "machine/createBond",
      meta: {
        model: "machine",
        method: "create_bond",
      },
      payload: {
        params: {
          bond_downdelay: 0,
          bond_mode: BondMode.ACTIVE_BACKUP,
          bond_miimon: 0,
          bond_updelay: 0,
          fabric: 1,
          mac_address: "00:00:00:00:00:15",
          name: "bond0",
          parents: [9, 10],
          system_id: "abc123",
          tags: [],
          vlan: 1,
        },
      },
    });
  });
});
