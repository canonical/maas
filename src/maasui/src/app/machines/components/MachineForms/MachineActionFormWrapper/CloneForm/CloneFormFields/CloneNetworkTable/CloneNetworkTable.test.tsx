import CloneNetworkTable from "./CloneNetworkTable";

import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, within } from "@/testing/utils";

describe("CloneNetworkTable", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      fabric: factory.fabricState({
        loaded: true,
      }),
      machine: factory.machineState({
        items: [factory.machineDetails({ system_id: "abc123" })],
        loaded: true,
        statuses: {
          abc123: factory.machineStatus(),
        },
      }),
      subnet: factory.subnetState({
        loaded: true,
      }),
      vlan: factory.vlanState({
        loaded: true,
      }),
    });
  });

  it("renders empty table if neither loading machine nor machine provided", () => {
    renderWithProviders(<CloneNetworkTable machine={null} selected={false} />, {
      state,
    });

    // should only be the single empty state cell from GenericTable
    expect(screen.getAllByRole("cell")).toHaveLength(1);
  });

  it("renders machine network details if machine is provided", () => {
    const machine = factory.machineDetails({
      interfaces: [factory.machineInterface({ name: "eth0" })],
    });

    renderWithProviders(
      <CloneNetworkTable machine={machine} selected={false} />,
      {
        state,
      }
    );

    expect(screen.getAllByRole("row")).toHaveLength(2);
    expect(screen.getByText("eth0")).toBeInTheDocument();
  });

  it("can display an interface that has no links", () => {
    const fabric = factory.fabric({ name: "fabric-name" });
    const vlan = factory.vlan({ fabric: fabric.id, vid: 2, name: "vlan-name" });
    const subnets = [
      factory.subnet({ cidr: "subnet-cidr", name: "subnet-name" }),
      factory.subnet({ cidr: "subnet2-cidr", name: "subnet2-name" }),
    ];
    const machine = factory.machineDetails({
      interfaces: [
        factory.machineInterface({
          discovered: null,
          links: [],
          type: NetworkInterfaceTypes.BOND,
          vlan_id: vlan.id,
        }),
      ],
      system_id: "abc123",
    });
    state.fabric.items = [fabric];
    state.machine.items = [machine];
    state.subnet.items = subnets;
    state.vlan.items = [vlan];

    renderWithProviders(<CloneNetworkTable machine={machine} selected />, {
      state,
    });

    expect(
      within(screen.getAllByRole("row")[1]).getAllByRole("cell")[0]
    ).toHaveTextContent("Unconfigured");
  });

  it("can display an interface that has a link", () => {
    const fabric = factory.fabric({ name: "fabric-name" });
    const vlan = factory.vlan({ fabric: fabric.id, vid: 2, name: "vlan-name" });
    const subnet = factory.subnet({ cidr: "subnet-cidr", name: "subnet-name" });
    const machine = factory.machineDetails({
      interfaces: [
        factory.machineInterface({
          discovered: null,
          links: [
            factory.networkLink({
              subnet_id: subnet.id,
              ip_address: "1.2.3.99",
            }),
          ],
          type: NetworkInterfaceTypes.BOND,
          vlan_id: vlan.id,
        }),
      ],
      system_id: "abc123",
    });
    state.fabric.items = [fabric];
    state.machine.items = [machine];
    state.subnet.items = [subnet];
    state.vlan.items = [vlan];

    renderWithProviders(<CloneNetworkTable machine={machine} selected />, {
      state,
    });

    expect(
      within(screen.getAllByRole("row")[1]).getAllByRole("cell")[0]
    ).toHaveTextContent("subnet-cidr");
  });

  it("can display an interface that is an alias", () => {
    const fabric = factory.fabric({ name: "fabric-name" });
    const vlan = factory.vlan({ fabric: fabric.id, vid: 2, name: "vlan-name" });
    const subnets = [
      factory.subnet({ cidr: "subnet-cidr", name: "subnet-name" }),
      factory.subnet({ cidr: "subnet2-cidr", name: "subnet2-name" }),
    ];
    const machine = factory.machineDetails({
      interfaces: [
        factory.machineInterface({
          discovered: null,
          links: [
            factory.networkLink({
              subnet_id: subnets[0].id,
              ip_address: "1.2.3.99",
            }),
            factory.networkLink({
              subnet_id: subnets[1].id,
              ip_address: "1.2.3.101",
            }),
          ],
          name: "alias",
          type: NetworkInterfaceTypes.ALIAS,
          vlan_id: vlan.id,
        }),
      ],
      system_id: "abc123",
    });
    state.fabric.items = [fabric];
    state.machine.items = [machine];
    state.subnet.items = subnets;
    state.vlan.items = [vlan];

    renderWithProviders(<CloneNetworkTable machine={machine} selected />, {
      state,
    });

    const cell = within(screen.getAllByRole("row")[2]).getAllByRole("cell")[0];

    expect(within(cell).getByTestId("primary")).toHaveTextContent("alias:1");
    expect(within(cell).getByTestId("secondary")).toHaveTextContent(
      "subnet2-cidr"
    );
  });

  it("groups bonds and bridges with their parent interfaces", () => {
    const machine = factory.machineDetails({
      interfaces: [
        factory.machineInterface({
          id: 100,
          name: "bond0",
          parents: [101, 104],
          type: NetworkInterfaceTypes.BOND,
        }),
        factory.machineInterface({
          children: [100],
          id: 101,
          name: "eth0",
          type: NetworkInterfaceTypes.PHYSICAL,
        }),
        factory.machineInterface({
          id: 102,
          links: [factory.networkLink(), factory.networkLink()],
          name: "br0",
          parents: [103],
          type: NetworkInterfaceTypes.BRIDGE,
        }),
        factory.machineInterface({
          children: [102],
          id: 103,
          name: "eth1",
          type: NetworkInterfaceTypes.PHYSICAL,
        }),
        factory.machineInterface({
          id: 99,
          name: "eth2",
          parents: [],
          type: NetworkInterfaceTypes.PHYSICAL,
        }),
        factory.machineInterface({
          children: [100],
          id: 104,
          name: "eth3",
          type: NetworkInterfaceTypes.PHYSICAL,
        }),
      ],
      system_id: "abc123",
    });
    state.machine.items = [machine];

    renderWithProviders(<CloneNetworkTable machine={machine} selected />, {
      state,
    });

    const dataRows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole(
      "row"
    );
    const names = dataRows.map(
      (row) =>
        within(within(row).getAllByRole("cell")[0]).getByTestId("primary")
          .textContent
    );

    expect(names).toStrictEqual([
      // Bond group:
      "bond0",
      "eth0", // bond parent
      "eth3", // bond parent
      // Bridge group:
      "br0",
      "eth1", // bridge parent
      // Alias:
      "br0:1",
      // Physical:
      "eth2",
    ]);
  });
});
