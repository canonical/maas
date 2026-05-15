import SubnetColumn from "./SubnetColumn";

import type { RootState } from "@/app/store/root/types";
import { NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("SubnetColumn", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      subnet: factory.subnetState({
        loaded: true,
      }),
    });
  });

  it("can display subnet links", () => {
    const fabric = factory.fabric({ name: "fabric-name" });
    state.fabric.items = [fabric];
    const vlan = factory.vlan({ fabric: fabric.id, vid: 2, name: "vlan-name" });
    const subnet = factory.subnet({ cidr: "subnet-cidr", name: "subnet-name" });
    state.vlan.items = [vlan];
    state.subnet.items = [subnet];
    const link = factory.networkLink({ subnet_id: subnet.id });
    const nic = factory.machineInterface({
      discovered: null,
      links: [link],
      vlan_id: vlan.id,
    });
    state.machine.items = [
      factory.machineDetails({
        interfaces: [nic],
        system_id: "abc123",
      }),
    ];
    renderWithProviders(
      <SubnetColumn link={link} nic={nic} node={state.machine.items[0]} />,
      { state }
    );

    expect(
      screen.getByRole("link", { name: "subnet-cidr" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "subnet-name" })
    ).toBeInTheDocument();
  });

  it("can display subnet links if the node is a device", () => {
    const fabric = factory.fabric({ name: "fabric-name" });
    state.fabric.items = [fabric];
    const vlan = factory.vlan({ fabric: fabric.id, vid: 2, name: "vlan-name" });
    const subnet = factory.subnet({ cidr: "subnet-cidr", name: "subnet-name" });
    state.vlan.items = [vlan];
    state.subnet.items = [subnet];
    const link = factory.networkLink({ subnet_id: subnet.id });
    const nic = factory.deviceInterface({
      discovered: null,
      links: [link],
      vlan_id: vlan.id,
    });
    state.device.items = [
      factory.deviceDetails({
        interfaces: [nic],
        system_id: "abc123",
      }),
    ];
    renderWithProviders(
      <SubnetColumn link={link} nic={nic} node={state.device.items[0]} />,
      { state }
    );

    expect(
      screen.getByRole("link", { name: "subnet-cidr" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "subnet-name" })
    ).toBeInTheDocument();
  });

  it("can display an unconfigured subnet", () => {
    const fabric = factory.fabric({ name: "fabric-name" });
    state.fabric.items = [fabric];
    const vlan = factory.vlan({ fabric: fabric.id, vid: 2, name: "vlan-name" });
    state.vlan.items = [vlan];
    const link = factory.networkLink();
    const nic = factory.machineInterface({
      discovered: null,
      links: [link],
      vlan_id: vlan.id,
    });
    state.machine.items = [
      factory.machineDetails({
        interfaces: [nic],
        system_id: "abc123",
      }),
    ];
    renderWithProviders(
      <SubnetColumn link={link} nic={nic} node={state.machine.items[0]} />,
      { state }
    );

    expect(screen.getByTestId("primary")).toHaveTextContent("Unconfigured");
  });

  it("can display the subnet name only", () => {
    const fabric = factory.fabric({ name: "fabric-name" });
    state.fabric.items = [fabric];
    const vlan = factory.vlan({ fabric: fabric.id, vid: 2, name: "vlan-name" });
    const subnet = factory.subnet({ cidr: "subnet-cidr", name: "subnet-name" });
    state.vlan.items = [vlan];
    state.subnet.items = [subnet];
    const discovered = [factory.networkDiscoveredIP({ subnet_id: subnet.id })];
    const nic = factory.machineInterface({
      discovered,
      links: [],
      vlan_id: vlan.id,
    });
    state.machine.items = [
      factory.machineDetails({
        interfaces: [nic],
        status: NodeStatus.DEPLOYING,
        system_id: "abc123",
      }),
    ];
    renderWithProviders(
      <SubnetColumn nic={nic} node={state.machine.items[0]} />,
      { state }
    );

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByTestId("primary")).toHaveTextContent(
      "subnet-cidr (subnet-name)"
    );
  });
});
