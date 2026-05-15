import EditBondForm from "./EditBondForm";

import {
  BondLacpRate,
  BondMode,
  BondXmitHashPolicy,
} from "@/app/store/general/types";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes, NetworkLinkMode } from "@/app/store/types/enum";
import type { NetworkInterface } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  within,
} from "@/testing/utils";

describe("EditBondForm", () => {
  let state: RootState;
  let nic: NetworkInterface;

  beforeEach(() => {
    nic = factory.machineInterface({
      type: NetworkInterfaceTypes.BOND,
      vlan_id: 1,
    });
    state = factory.rootState({
      fabric: factory.fabricState({
        loaded: true,
        items: [factory.fabric({ name: "test-fabric", id: 1 })],
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
      subnet: factory.subnetState({
        items: [factory.subnet({ id: 1, name: "test-subnet-1", vlan: 1 })],
        loaded: true,
      }),
      vlan: factory.vlanState({
        items: [
          factory.vlan({
            id: 1,
            fabric: 1,
          }),
        ],
        loaded: true,
      }),
    });
  });

  it("displays a table", () => {
    const interfaces = [
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
    nic.parents = [interfaces[0].id, interfaces[1].id];
    renderWithProviders(
      <EditBondForm
        nic={nic}
        selected={[]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );
    expect(screen.getByRole("grid")).toBeInTheDocument();
  });

  it("displays the selected interfaces when not editing members", () => {
    const interfaces = [
      factory.machineInterface({
        name: "eth0",
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
      }),
      factory.machineInterface({
        name: "eth1",
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
    nic.parents = [interfaces[0].id, interfaces[1].id];
    renderWithProviders(
      <EditBondForm
        nic={nic}
        selected={selected}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );
    const rows = screen.getAllByRole("row");
    expect(within(rows[1]).getByTestId("name")).toHaveTextContent("eth0");
    expect(within(rows[2]).getByTestId("name")).toHaveTextContent("eth1");
  });

  it("displays all valid interfaces when editing members", async () => {
    const interfaces = [
      factory.machineInterface({
        name: "valid0",
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
      }),
      factory.machineInterface({
        name: "valid1",
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
      }),
      // VLANs are not valid.
      factory.machineInterface({
        name: "notvalid0",
        type: NetworkInterfaceTypes.VLAN,
        vlan_id: 1,
      }),
      // Bridges are not valid.
      factory.machineInterface({
        name: "notvalid1",
        type: NetworkInterfaceTypes.BRIDGE,
        vlan_id: 1,
      }),
      // Bonds are not valid.
      factory.machineInterface({
        name: "notvalid2",
        type: NetworkInterfaceTypes.BOND,
        vlan_id: 1,
      }),
      // Physical interfaces in other VLANs are not valid.
      factory.machineInterface({
        name: "notvalid3",
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 2,
      }),
      // Physical interfaces in the same VLAN are valid.
      factory.machineInterface({
        name: "valid2",
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
    renderWithProviders(
      <EditBondForm
        nic={nic}
        selected={[{ nicId: interfaces[0].id }, { nicId: interfaces[1].id }]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Edit bond members" })
    );

    const rows = screen.getAllByRole("row");
    expect(within(rows[1]).getByTestId("name")).toHaveTextContent("valid0");
    expect(within(rows[2]).getByTestId("name")).toHaveTextContent("valid1");
    expect(within(rows[3]).getByTestId("name")).toHaveTextContent("valid2");

    expect(screen.queryByText("notvalid0")).not.toBeInTheDocument();
    expect(screen.queryByText("notvalid1")).not.toBeInTheDocument();
    expect(screen.queryByText("notvalid2")).not.toBeInTheDocument();
    expect(screen.queryByText("notvalid3")).not.toBeInTheDocument();
  });

  it("disables the submit button if two interfaces aren't selected", async () => {
    const interfaces = [
      factory.machineInterface({
        name: "eth0",
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
      }),
      factory.machineInterface({
        name: "eth1",
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: 1,
      }),
      factory.machineInterface({
        name: "eth2",
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
    nic.parents = [interfaces[0].id, interfaces[1].id];
    renderWithProviders(
      <EditBondForm
        nic={nic}
        selected={[]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Edit bond members" })
    );
    // Select eth2 to make membersHaveChanged=true → submit becomes enabled.
    await userEvent.click(
      screen.getByRole("checkbox", { name: "select eth2" })
    );
    expect(
      screen.getByRole("button", { name: "Save interface" })
    ).not.toBeDisabled();
    // Deselect eth0 and eth1, leaving only eth2 → fewer than two selected → disabled.
    await userEvent.click(
      screen.getByRole("checkbox", { name: "select eth0" })
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: "select eth1" })
    );
    expect(
      screen.getByRole("button", { name: "Save interface" })
    ).toBeDisabled();
  });

  it("enables the submit button if only the members have changed", async () => {
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
        name: "eth2",
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
    nic.parents = [interfaces[0].id, interfaces[1].id];
    renderWithProviders(
      <EditBondForm
        nic={nic}
        selected={[]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );
    expect(
      screen.getByRole("button", { name: "Save interface" })
    ).toBeDisabled();
    await userEvent.click(
      screen.getByRole("button", { name: "Edit bond members" })
    );
    // Select an extra interface — membersHaveChanged becomes true → submit enabled.
    await userEvent.click(
      screen.getByRole("checkbox", { name: "select eth2" })
    );
    expect(
      screen.getByRole("button", { name: "Save interface" })
    ).not.toBeDisabled();
  });

  it("fetches the necessary data on load", async () => {
    const { store } = renderWithProviders(
      <EditBondForm
        nic={nic}
        selected={[]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
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
      <EditBondForm
        nic={nic}
        selected={[]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );
    expect(screen.getByText("Loading")).toBeInTheDocument();
  });

  it("can dispatch an action to update a bond", async () => {
    const bond = factory.machineInterface({
      id: 3,
      name: "bond1",
      parents: [9, 10],
      type: NetworkInterfaceTypes.BOND,
      vlan_id: 1,
      params: {
        bond_xmit_hash_policy: BondXmitHashPolicy.LAYER2,
        bond_lacp_rate: BondLacpRate.FAST,
      },
    });
    state.general.bondOptions.loaded = true;
    state.general.bondOptions.data = factory.bondOptions({
      lacp_rates: [
        [BondLacpRate.FAST, BondLacpRate.FAST],
        [BondLacpRate.SLOW, BondLacpRate.SLOW],
      ],
      modes: [
        [BondMode.BALANCE_RR, BondMode.BALANCE_RR],
        [BondMode.ACTIVE_BACKUP, BondMode.ACTIVE_BACKUP],
        [BondMode.BALANCE_XOR, BondMode.BALANCE_XOR],
        [BondMode.BROADCAST, BondMode.BROADCAST],
        [BondMode.LINK_AGGREGATION, BondMode.LINK_AGGREGATION],
        [BondMode.BALANCE_TLB, BondMode.BALANCE_TLB],
        [BondMode.BALANCE_ALB, BondMode.BALANCE_ALB],
      ],
    });
    state.machine.items = [
      factory.machineDetails({
        interfaces: [
          bond,
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
    const link = { id: 1, subnet_id: 1, mode: NetworkLinkMode.AUTO };
    const { store } = renderWithProviders(
      <EditBondForm
        link={link}
        nic={bond}
        selected={[{ nicId: 9 }, { nicId: 10 }]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Subnet" }),
      screen.getByRole("option", { name: /test-subnet-1/ })
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
          bond_downdelay: 0,
          bond_lacp_rate: "fast",
          bond_mode: BondMode.ACTIVE_BACKUP,
          bond_miimon: 0,
          bond_updelay: 0,
          bond_xmit_hash_policy: BondXmitHashPolicy.LAYER2,
          fabric: 1,
          interface_id: bond.id,
          link_id: 1,
          mac_address: "00:00:00:00:00:26",
          mode: NetworkLinkMode.LINK_UP,
          name: "bond1",
          parents: [9, 10],
          subnet: "1",
          system_id: "abc123",
          tags: [],
          vlan: 1,
        },
      },
    });
  });
});
