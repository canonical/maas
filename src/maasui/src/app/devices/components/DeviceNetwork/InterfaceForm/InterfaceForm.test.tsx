import InterfaceForm from "./InterfaceForm";

import type { DeviceNetworkInterface } from "@/app/store/device/types";
import { DeviceIpAssignment } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("InterfaceForm", () => {
  let state: RootState;
  let nic: DeviceNetworkInterface;
  beforeEach(() => {
    nic = factory.deviceInterface();
    state = factory.rootState({
      device: factory.deviceState({
        items: [
          factory.deviceDetails({
            system_id: "abc123",
          }),
        ],
        loaded: true,
        statuses: factory.deviceStatuses({
          abc123: factory.deviceStatus(),
        }),
      }),
      subnet: factory.subnetState({
        items: [factory.subnet({ id: 1 }), factory.subnet({ id: 2 })],
        loaded: true,
      }),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("displays a spinner if device is not detailed version", () => {
    state.device.items[0] = factory.device({ system_id: "abc123" });

    renderWithProviders(
      <InterfaceForm nicId={nic.id} onSubmit={vi.fn()} systemId="abc123" />,
      { state }
    );

    expect(screen.getByTestId("loading-device-details")).toBeInTheDocument();
  });

  it("prefills the initial data if an existing nic is provided", () => {
    const nicData = {
      ip_address: "192.168.1.1",
      ip_assignment: DeviceIpAssignment.STATIC,
      mac_address: "11:22:33:44:55:66",
      name: "eth123",
      tags: ["tag1", "tag2"],
    };
    const fabric = factory.fabric({ name: "fabric-name" });
    state.fabric.items = [fabric];
    const vlan = factory.vlan({ fabric: fabric.id, vid: 2, name: "vlan-name" });
    state.vlan.items = [vlan];
    const subnet = factory.subnet({ cidr: "subnet-cidr", name: "subnet-name" });
    state.subnet.items = [subnet];
    const link = factory.networkLink({ subnet_id: subnet.id });
    nic = factory.deviceInterface({
      ...nicData,
      discovered: [],
      links: [link],
      type: NetworkInterfaceTypes.PHYSICAL,
      vlan_id: vlan.id,
    });
    state.device.items = [
      factory.deviceDetails({
        interfaces: [nic],
        system_id: "abc123",
      }),
    ];

    renderWithProviders(
      <InterfaceForm
        linkId={link.id}
        nicId={nic.id}
        onSubmit={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("eth123");
    expect(screen.getByRole("textbox", { name: "Type" })).toHaveValue(
      "Physical"
    );
    expect(screen.getByRole("textbox", { name: "MAC address" })).toHaveValue(
      "11:22:33:44:55:66"
    );
    const tags = screen.getAllByTestId("selected-tag");
    expect(tags[0]).toHaveTextContent("tag1");
    expect(tags[1]).toHaveTextContent("tag2");

    expect(screen.getByRole("combobox", { name: "IP assignment" })).toHaveValue(
      DeviceIpAssignment.STATIC
    );
    expect(screen.getByRole("combobox", { name: "Subnet" })).toHaveValue("20");
    expect(screen.getByRole("textbox", { name: "IP address" })).toHaveValue(
      "192.168.1.1"
    );
  });

  it("sets the initial data if no nic is provided", () => {
    state.device.items[0] = factory.deviceDetails({
      interfaces: [factory.deviceInterface({ name: "eth20" })],
      system_id: "abc123",
    });

    renderWithProviders(
      <InterfaceForm onSubmit={vi.fn()} systemId="abc123" />,
      { state }
    );
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("eth21");
    expect(screen.getByRole("textbox", { name: "Type" })).toHaveValue(
      "Physical"
    );
    expect(screen.getByRole("textbox", { name: "MAC address" })).toHaveValue(
      ""
    );
    expect(screen.getByRole("combobox", { name: "IP assignment" })).toHaveValue(
      DeviceIpAssignment.DYNAMIC
    );
    expect(screen.queryByTestId("selected-tags")).not.toBeInTheDocument();
  });
});
