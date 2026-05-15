import AddAliasOrVlan, {
  Labels as AddAliasOrVlanLabels,
} from "./AddAliasOrVlan";

import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes, NetworkLinkMode } from "@/app/store/types/enum";
import {
  NodeStatus,
  NodeStatusCode,
  TestStatusStatus,
} from "@/app/store/types/node";
import type { NetworkInterface } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  expectTooltipOnHover,
  renderWithProviders,
} from "@/testing/utils";

describe("AddAliasOrVlan", () => {
  let state: RootState;
  let nic: NetworkInterface;
  beforeEach(() => {
    nic = factory.machineInterface();
    state = factory.rootState({
      fabric: factory.fabricState({
        items: [factory.fabric({ id: 54 })],
      }),
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machineDetails({
            actions: [],
            architecture: "amd64/generic",
            cpu_count: 4,
            cpu_test_status: factory.testStatus({
              status: TestStatusStatus.RUNNING,
            }),
            distro_series: "bionic",
            domain: factory.modelRef({
              name: "example",
            }),
            extra_macs: [],
            fqdn: "koala.example",
            hostname: "koala",
            interfaces: [nic],
            ip_addresses: [],
            memory: 8,
            memory_test_status: factory.testStatus({
              status: TestStatusStatus.PASSED,
            }),
            network_test_status: factory.testStatus({
              status: TestStatusStatus.PASSED,
            }),
            osystem: "ubuntu",
            owner: "admin",
            permissions: ["edit", "delete"],
            physical_disk_count: 1,
            pool: factory.modelRef(),
            pxe_mac: "00:11:22:33:44:55",
            spaces: [],
            status: NodeStatus.DEPLOYED,
            status_code: NodeStatusCode.DEPLOYED,
            status_message: "",
            storage: 8,
            storage_test_status: factory.testStatus({
              status: TestStatusStatus.PASSED,
            }),
            testing_status: TestStatusStatus.PASSED,
            system_id: "abc123",
            zone: factory.modelRef(),
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
      vlan: factory.vlanState({
        items: [factory.vlan({ id: nic.vlan_id })],
      }),
    });
  });

  it("displays a spinner when data is loading", () => {
    state.machine.items = [];
    renderWithProviders(
      <AddAliasOrVlan
        interfaceType={NetworkInterfaceTypes.VLAN}
        nic={nic}
        systemId="abc123"
      />,
      { state }
    );
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("displays a save-another button for aliases", () => {
    renderWithProviders(
      <AddAliasOrVlan
        interfaceType={NetworkInterfaceTypes.ALIAS}
        nic={nic}
        systemId="abc123"
      />,
      { state }
    );
    const secondarySubmit = screen.getByRole("button", {
      name: AddAliasOrVlanLabels.SaveAndAdd,
    });
    expect(secondarySubmit).not.toBeAriaDisabled();
  });

  it("displays a save-another button when there are unused VLANS", () => {
    const fabric = factory.fabric();
    state.fabric.items = [fabric];
    const vlan = factory.vlan({ fabric: fabric.id });
    state.vlan.items = [vlan, factory.vlan({ fabric: fabric.id })];
    const nic = factory.machineInterface({
      type: NetworkInterfaceTypes.PHYSICAL,
      vlan_id: vlan.id,
    });
    state.machine.items = [
      factory.machineDetails({
        interfaces: [nic],
        system_id: "abc123",
      }),
    ];
    renderWithProviders(
      <AddAliasOrVlan
        interfaceType={NetworkInterfaceTypes.VLAN}
        nic={nic}
        systemId="abc123"
      />,
      { state }
    );
    expect(
      screen.getByRole("button", {
        name: AddAliasOrVlanLabels.SaveAndAdd,
      })
    ).toBeInTheDocument();
  });

  it("disables the save-another button when there are no unused VLANS", async () => {
    state.vlan.items = [factory.vlan({ id: nic.vlan_id })];
    renderWithProviders(
      <AddAliasOrVlan
        interfaceType={NetworkInterfaceTypes.VLAN}
        nic={nic}
        systemId="abc123"
      />,
      { state }
    );
    const saveAndAddButton = screen.getByRole("button", {
      name: AddAliasOrVlanLabels.SaveAndAdd,
    });
    expect(saveAndAddButton).toBeAriaDisabled();
    await expectTooltipOnHover(
      saveAndAddButton,
      "There are no more unused VLANS for this interface."
    );
  });

  it("correctly initialises fabric and VLAN when adding an alias", () => {
    const fabric = factory.fabric({ id: 1 });
    const vlan = factory.vlan({ fabric: fabric.id, id: 5001 });
    const nic = factory.machineInterface({ vlan_id: vlan.id });
    const machine = factory.machineDetails({
      system_id: "abc123",
      interfaces: [nic],
    });
    const state = factory.rootState({
      fabric: factory.fabricState({
        items: [fabric],
        loaded: true,
        loading: false,
      }),
      machine: factory.machineState({
        items: [machine],
        statuses: factory.machineStatuses({
          [machine.system_id]: factory.machineStatus(),
        }),
      }),
      vlan: factory.vlanState({
        items: [vlan],
        loaded: true,
        loading: false,
      }),
    });
    renderWithProviders(
      <AddAliasOrVlan
        interfaceType={NetworkInterfaceTypes.ALIAS}
        nic={nic}
        systemId="abc123"
      />,
      { state }
    );

    expect(screen.getByRole("combobox", { name: "Fabric" })).toHaveValue(
      `${fabric.id}`
    );
    expect(screen.getByRole("combobox", { name: "VLAN" })).toHaveValue(
      `${vlan.id}`
    );
  });

  it("correctly dispatches actions to add a VLAN", async () => {
    const nic = factory.machineInterface();
    state.vlan.items = [factory.vlan({ id: nic.vlan_id })];
    const { store } = renderWithProviders(
      <AddAliasOrVlan
        interfaceType={NetworkInterfaceTypes.VLAN}
        nic={nic}
        systemId="abc123"
      />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("button", { name: AddAliasOrVlanLabels.SaveInterface })
    );

    expect(
      store.getActions().find((action) => action.type === "machine/createVlan")
    ).toStrictEqual({
      type: "machine/createVlan",
      meta: {
        model: "machine",
        method: "create_vlan",
      },
      payload: {
        params: {
          fabric: "54",
          parent: nic.id,
          system_id: "abc123",
          tags: [],
          vlan: 5001,
        },
      },
    });
  });

  it("correctly dispatches actions to add an alias", async () => {
    const fabric = factory.fabric({ id: 1 });
    const vlan = factory.vlan({ fabric: fabric.id, id: 5001 });
    const nic = factory.machineInterface({ vlan_id: vlan.id });
    const machine = factory.machineDetails({
      system_id: "abc123",
      interfaces: [nic],
    });
    const state = factory.rootState({
      fabric: factory.fabricState({
        items: [fabric],
        loaded: true,
        loading: false,
      }),
      machine: factory.machineState({
        items: [machine],
        statuses: factory.machineStatuses({
          [machine.system_id]: factory.machineStatus(),
        }),
      }),
      vlan: factory.vlanState({
        items: [vlan],
        loaded: true,
        loading: false,
      }),
      subnet: factory.subnetState({
        items: [factory.subnet({ id: 76, vlan: vlan.id })],
        loaded: true,
      }),
    });
    const { store } = renderWithProviders(
      <AddAliasOrVlan
        interfaceType={NetworkInterfaceTypes.ALIAS}
        nic={nic}
        systemId="abc123"
      />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("button", { name: AddAliasOrVlanLabels.SaveInterface })
    );

    expect(
      store.getActions().find((action) => action.type === "machine/linkSubnet")
    ).toStrictEqual({
      type: "machine/linkSubnet",
      meta: {
        model: "machine",
        method: "link_subnet",
      },
      payload: {
        params: {
          fabric: 1,
          interface_id: nic.id,
          mode: NetworkLinkMode.AUTO,
          subnet: "76",
          system_id: "abc123",
          vlan: 5001,
        },
      },
    });
  });
});
