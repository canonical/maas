import EditInterface from "../EditInterface";

import DeviceNetworkTable from "./DeviceNetworkTable";
import RemoveInterface from "./RemoveInterface";

import type { DeviceDetails } from "@/app/store/device/types";
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

const { mockOpen } = await mockSidePanel();

vi.mock("@/app/base/side-panel-context", async () => {
  const actual = await vi.importActual("@/app/base/side-panel-context");
  return {
    ...actual,
    useSidePanel: vi.fn(),
  };
});

describe("DeviceNetworkTable", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      fabric: factory.fabricState({
        loaded: true,
      }),
      device: factory.deviceState({
        items: [factory.deviceDetails({ system_id: "abc123" })],
        loaded: true,
        statuses: {
          abc123: factory.deviceStatus(),
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
    it("displays a spinner when loading", () => {
      state.device.items = [];

      renderWithProviders(<DeviceNetworkTable systemId="abc123" />, { state });
      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    it("displays a table when loaded", () => {
      renderWithProviders(<DeviceNetworkTable systemId="abc123" />, { state });

      expect(screen.getByRole("grid")).toBeInTheDocument();
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<DeviceNetworkTable systemId="abc123" />, { state });

      ["Mac", "Subnet", "IP address", "IP assignment", "Actions"].forEach(
        (column) => {
          expect(
            screen.getByRole("columnheader", {
              name: new RegExp(`^${column}`, "i"),
            })
          ).toBeInTheDocument();
        }
      );
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
      const subnets = [
        factory.subnet({ cidr: "subnet-cidr", name: "subnet-name" }),
        factory.subnet({ cidr: "subnet2-cidr", name: "subnet2-name" }),
      ];
      state.subnet.items = subnets;
      state.device.items = [
        factory.deviceDetails({
          interfaces: [
            factory.deviceInterface({
              discovered: null,
              links: [],
              type: NetworkInterfaceTypes.BOND,
              vlan_id: vlan.id,
            }),
          ],
          system_id: "abc123",
        }),
      ];

      renderWithProviders(<DeviceNetworkTable systemId="abc123" />, { state });
      expect(
        within(screen.getAllByRole("row")[1]).getAllByRole("cell")[3]
      ).toHaveTextContent("Unconfigured");
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
      state.device.items = [
        factory.deviceDetails({
          interfaces: [
            factory.deviceInterface({
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
        }),
      ];

      renderWithProviders(<DeviceNetworkTable systemId="abc123" />, { state });
      expect(
        screen.getByRole("link", { name: "subnet-cidr" })
      ).toBeInTheDocument();
      expect(screen.getByText("1.2.3.99")).toBeInTheDocument();
    });

    it("displays an empty table description", () => {
      state.device.items = [
        factory.deviceDetails({
          interfaces: [],
          system_id: "abc123",
        }),
      ];

      renderWithProviders(<DeviceNetworkTable systemId="abc123" />, { state });
      expect(screen.getByText("No interfaces available.")).toBeInTheDocument();
    });
  });

  describe("permissions", () => {
    it.todo("enables the action buttons with correct permissions");

    it.todo("disables the action buttons without permissions");
  });

  describe("actions", () => {
    let device: DeviceDetails;
    beforeEach(() => {
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
      device = factory.deviceDetails({
        interfaces: [
          factory.deviceInterface({
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
      state.subnet.items = [subnet];
      state.device.items = [device];
    });

    it("opens the edit interface side panel", async () => {
      renderWithProviders(<DeviceNetworkTable systemId="abc123" />, {
        state,
      });

      await userEvent.click(screen.getByRole("button", { name: "Edit" }));

      await waitFor(() => {
        expect(mockOpen).toHaveBeenCalledWith({
          component: EditInterface,
          title: "Edit interface",
          props: {
            nicId: device.interfaces[0].id,
            linkId: device.interfaces[0].links[0].id,
            systemId: device.system_id,
          },
        });
      });
    });

    it("opens the delete interface side panel", async () => {
      renderWithProviders(<DeviceNetworkTable systemId="abc123" />, {
        state,
      });

      await userEvent.click(screen.getByRole("button", { name: "Delete" }));

      await waitFor(() => {
        expect(mockOpen).toHaveBeenCalledWith({
          component: RemoveInterface,
          title: "Remove interface",
          props: {
            nicId: device.interfaces[0].id,
            systemId: device.system_id,
          },
        });
      });
    });
  });
});
