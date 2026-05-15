import DHCPTable from "./DHCPTable";

import DhcpEdit from "@/app/settings/views/Dhcp/DhcpEdit";
import { MachineMeta } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("DHCPTable", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        loaded: true,
        loading: false,
        items: [
          factory.dhcpSnippet({ node: "abc123" }),
          factory.dhcpSnippet({ node: "abc123" }),
          factory.dhcpSnippet(),
        ],
      }),
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            architecture: "amd64",
            events: [factory.machineEvent()],
            system_id: "abc123",
          }),
        ],
        loaded: true,
        loading: false,
      }),
    });
  });

  describe("display", () => {
    it("displays the required columns", () => {
      renderWithProviders(
        <DHCPTable
          modelName={MachineMeta.MODEL}
          node={state.machine.items[0]}
        />,
        {
          initialEntries: [{ pathname: "/machine/abc123", key: "testKey" }],
          state,
        }
      );

      [
        "Name",
        "Type",
        "Applies To",
        "Enabled",
        "Description",
        "Actions",
      ].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });

    it("shows a message when there are no snippets", () => {
      state.dhcpsnippet.items = [];
      renderWithProviders(
        <DHCPTable
          modelName={MachineMeta.MODEL}
          node={state.machine.items[0]}
        />,
        {
          initialEntries: [{ pathname: "/machine/abc123", key: "testKey" }],
          state,
        }
      );

      expect(
        screen.getByText("No DHCP snippets applied to this machine.")
      ).toBeInTheDocument();
    });

    it("shows loading state for snippets", () => {
      state.dhcpsnippet.loading = true;
      state.dhcpsnippet.loaded = false;
      state.dhcpsnippet.items = [];

      renderWithProviders(
        <DHCPTable
          modelName={MachineMeta.MODEL}
          node={state.machine.items[0]}
        />,
        {
          initialEntries: [{ pathname: "/machine/abc123", key: "testKey" }],
          state,
        }
      );

      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    it("shows snippets for a machine", () => {
      state.machine.items = [
        factory.machineDetails({
          on_network: true,
          osystem: "ubuntu",
          status: NodeStatus.NEW,
          system_id: "abc123",
        }),
      ];

      renderWithProviders(
        <DHCPTable
          modelName={MachineMeta.MODEL}
          node={state.machine.items[0]}
        />,
        {
          initialEntries: [{ pathname: "/machine/abc123", key: "testKey" }],
          state,
        }
      );

      expect(screen.getAllByRole("row").length).toBe(3);
    });

    it("shows snippets for subnets", () => {
      const subnets = [
        factory.subnet({ name: "subnet-name1" }),
        factory.subnet({ name: "subnet-name2" }),
      ];
      state.dhcpsnippet.items = [
        factory.dhcpSnippet({ subnet: subnets[0].id }),
        factory.dhcpSnippet(),
        factory.dhcpSnippet({ subnet: subnets[1].id }),
      ];

      renderWithProviders(
        <DHCPTable modelName={MachineMeta.MODEL} subnets={subnets} />,
        {
          initialEntries: [{ pathname: "/machine/abc123", key: "testKey" }],
          state,
        }
      );
      const subnetSnippets = screen.getAllByRole("cell", {
        name: /subnet-name/,
      });

      expect(subnetSnippets.length).toBe(2);
      expect(subnetSnippets[0].textContent).toBe("subnet-name1");
      expect(subnetSnippets[1].textContent).toBe("subnet-name2");
    });
  });

  describe("table actions", () => {
    it("opens the side panel to edit a snippet", async () => {
      state.controller.loaded = true;
      state.device.loaded = true;
      state.machine.loaded = true;
      state.machine.items = [
        factory.machineDetails({
          on_network: true,
          osystem: "ubuntu",
          status: NodeStatus.NEW,
          system_id: "abc123",
        }),
      ];

      renderWithProviders(
        <DHCPTable
          modelName={MachineMeta.MODEL}
          node={state.machine.items[0]}
        />,
        {
          initialEntries: [{ pathname: "/machine/abc123", key: "testKey" }],
          state,
        }
      );
      const buttons = screen.getAllByRole("button", { name: "Edit" });

      await userEvent.click(buttons[buttons.length - 1]);

      expect(mockOpen).toHaveBeenCalledWith({
        component: DhcpEdit,
        props: { id: state.dhcpsnippet.items[1].id },
        title: "Edit DHCP Snippet",
      });
    });
  });
});
