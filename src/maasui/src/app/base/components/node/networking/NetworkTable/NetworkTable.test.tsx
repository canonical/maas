import NetworkTable from "@/app/base/components/node/networking/NetworkTable/NetworkTable";
import { Label as PXEColumnLabel } from "@/app/base/components/node/networking/NetworkTable/PXEColumn/PXEColumn";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

await mockSidePanel();

describe("NetworkTable", () => {
  let state: RootState;
  let machine: MachineDetails;
  beforeEach(() => {
    machine = factory.machineDetails({ system_id: "abc123" });
    state = factory.rootState({
      fabric: factory.fabricState({
        loaded: true,
      }),
      machine: factory.machineState({
        items: [machine],
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

  describe("display", () => {
    it("displays a loading component if zones are loading", async () => {
      const state = factory.rootState({
        fabric: factory.fabricState({
          loaded: false,
        }),
        machine: factory.machineState({
          items: [machine],
          loaded: true,
          statuses: {
            abc123: factory.machineStatus(),
          },
        }),
      });
      renderWithProviders(<NetworkTable node={machine} />, { state });

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      renderWithProviders(<NetworkTable node={machine} />, { state });

      await waitFor(() => {
        expect(
          screen.getByText("No interfaces available.")
        ).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(
        <NetworkTable
          node={machine}
          setExpanded={vi.fn()}
          setSelected={vi.fn()}
        />
      );

      [
        "Name",
        "PXE",
        "Link/Interface Speed",
        "Type",
        "Fabric",
        "Subnet",
        "IP Address",
        "DHCP",
        "Action",
      ].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });

    it("omits Actions column when setExpanded is not provided", () => {
      renderWithProviders(<NetworkTable node={machine} />);

      expect(
        screen.queryByRole("columnheader", {
          name: new RegExp(`^Action`, "i"),
        })
      ).not.toBeInTheDocument();
    });

    it("can display an interface that has no links", () => {
      const fabric = factory.fabric({ name: "fabric-name" });
      state.fabric.items = [fabric];
      const vlan = factory.vlan({
        fabric: fabric.id,
        vid: 2,
        name: "vlan-name",
      });
      state.vlan.items = [vlan];
      state.subnet.items = [
        factory.subnet({ cidr: "subnet-cidr", name: "subnet-name" }),
        factory.subnet({ cidr: "subnet2-cidr", name: "subnet2-name" }),
      ];
      machine = factory.machineDetails({
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
      state.machine.items = [machine];
      renderWithProviders(
        <NetworkTable
          node={machine}
          setExpanded={vi.fn()}
          setSelected={vi.fn()}
        />,
        { state }
      );

      const row = screen.getAllByRole("row")[1];
      const cells = within(row).getAllByRole("cell");
      const subnetCell = cells[6];
      expect(subnetCell).toHaveTextContent("Unconfigured");
      const ipCell = cells[7];
      expect(ipCell).toHaveTextContent("Unconfigured");
    });

    it("can display an interface that has a link", () => {
      const fabric = factory.fabric({ name: "fabric-name" });
      state.fabric.items = [fabric];
      const vlan = factory.vlan({
        fabric: fabric.id,
        vid: 2,
        name: "vlan-name",
      });
      state.vlan.items = [vlan];
      const subnet = factory.subnet({
        cidr: "subnet-cidr",
        name: "subnet-name",
      });
      state.subnet.items = [subnet];
      machine = factory.machineDetails({
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
      state.machine.items = [machine];
      renderWithProviders(
        <NetworkTable
          node={machine}
          setExpanded={vi.fn()}
          setSelected={vi.fn()}
        />,
        { state }
      );

      const row = screen.getAllByRole("row")[1];
      const cells = within(row).getAllByRole("cell");
      const subnetCell = cells[6];
      expect(subnetCell).toHaveTextContent("subnet-cidr");
      const ipCell = cells[7];
      expect(ipCell).toHaveTextContent("1.2.3.99");
    });

    it("can display an interface that is an alias", () => {
      const fabric = factory.fabric({ name: "fabric-name" });
      state.fabric.items = [fabric];
      const vlan = factory.vlan({
        fabric: fabric.id,
        vid: 2,
        name: "vlan-name",
      });
      state.vlan.items = [vlan];
      const subnets = [
        factory.subnet({ cidr: "subnet-cidr", name: "subnet-name" }),
        factory.subnet({ cidr: "subnet2-cidr", name: "subnet2-name" }),
      ];
      const ipAddresses = ["1.2.3.99", "1.2.3.101"];
      state.subnet.items = subnets;
      machine = factory.machineDetails({
        interfaces: [
          factory.machineInterface({
            discovered: null,
            links: [
              factory.networkLink({
                subnet_id: subnets[0].id,
                ip_address: ipAddresses[0],
              }),
              factory.networkLink({
                subnet_id: subnets[1].id,
                ip_address: ipAddresses[1],
              }),
            ],
            name: "alias",
            type: NetworkInterfaceTypes.ALIAS,
            vlan_id: vlan.id,
          }),
        ],
        system_id: "abc123",
      });
      state.machine.items = [machine];
      renderWithProviders(
        <NetworkTable
          node={machine}
          setExpanded={vi.fn()}
          setSelected={vi.fn()}
        />,
        { state }
      );

      const rows = screen.getAllByRole("row").slice(1);
      rows.forEach((row, index) => {
        const cells = within(row).getAllByRole("cell");
        const nameCell = cells[1];
        expect(nameCell).toHaveTextContent("alias");
        const subnetCell = cells[6];
        expect(subnetCell).toHaveTextContent(subnets[index].name);
        const ipCell = cells[7];
        expect(ipCell).toHaveTextContent(ipAddresses[index]);
      });
    });
  });

  describe("subrows", () => {
    beforeEach(() => {
      machine = factory.machineDetails({
        interfaces: [
          factory.machineInterface({
            id: 100,
            is_boot: false,
            name: "bond0",
            parents: [101],
            type: NetworkInterfaceTypes.BOND,
          }),
          factory.machineInterface({
            id: 101,
            children: [100],
            is_boot: true,
            name: "eth0",
            type: NetworkInterfaceTypes.PHYSICAL,
          }),
        ],
        system_id: "abc123",
      });
      state.machine.items = [machine];
    });

    it("does not display a checkbox for parent interfaces", () => {
      renderWithProviders(
        <NetworkTable
          node={machine}
          setExpanded={vi.fn()}
          setSelected={vi.fn()}
        />,
        { state }
      );

      const rows = screen.getAllByRole("row");
      const bondRow = rows[1];
      expect(within(bondRow).getByRole("checkbox")).toBeInTheDocument();
      const nicRow = rows[2];
      expect(within(nicRow).queryByRole("checkbox")).toBeDisabled();
    });

    it("does not include parent interfaces in the selection", async () => {
      const setSelected = vi.fn();
      renderWithProviders(
        <NetworkTable
          node={machine}
          setExpanded={vi.fn()}
          setSelected={setSelected}
        />,
        { state }
      );

      await userEvent.click(
        screen.getByRole("checkbox", { name: "select bond0" })
      );
      expect(setSelected).toHaveBeenCalledWith([{ linkId: null, nicId: 100 }]);
    });

    it("does not display a boot icon for parent interfaces", () => {
      renderWithProviders(
        <NetworkTable
          node={machine}
          setExpanded={vi.fn()}
          setSelected={vi.fn()}
        />,
        { state }
      );
      const row = screen.getAllByRole("row")[2];
      expect(
        within(row).queryByLabelText(PXEColumnLabel.IsBoot)
      ).not.toBeInTheDocument();
    });

    it("filters columns for parent interfaces", () => {
      renderWithProviders(
        <NetworkTable
          node={machine}
          setExpanded={vi.fn()}
          setSelected={vi.fn()}
        />,
        { state }
      );
      const row = screen.getAllByRole("row")[2];
      const cells = within(row).queryAllByRole("cell");
      const fabricCell = cells[5];
      expect(fabricCell).toHaveTextContent("");
      const subnetCell = cells[6];
      expect(subnetCell).toHaveTextContent("");
      const ipCell = cells[7];
      expect(ipCell).toHaveTextContent("");
      const dhcpCell = cells[8];
      expect(dhcpCell).toHaveTextContent("");
      const actionCell = cells[9];
      expect(actionCell).toHaveTextContent("");
    });
  });
});
