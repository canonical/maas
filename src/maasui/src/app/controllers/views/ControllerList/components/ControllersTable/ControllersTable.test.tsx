import ControllersTable from "./ControllersTable";

import urls from "@/app/base/urls";
import type { Controller } from "@/app/store/controller/types";
import type { RootState } from "@/app/store/root/types";
import { NodeType } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitForLoading,
  within,
} from "@/testing/utils";

describe("ControllersTable", () => {
  let controller: Controller;
  let state: RootState;
  beforeEach(() => {
    controller = factory.controller();
    state = factory.rootState({
      controller: factory.controllerState({
        loaded: true,
        items: [controller],
      }),
    });
  });

  it("displays a spinner while loading", () => {
    renderWithProviders(
      <ControllersTable
        controllers={[controller]}
        isPending={true}
        rowSelection={{}}
        setRowSelection={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("links to a controller's details page", () => {
    controller.system_id = "def456";
    renderWithProviders(
      <ControllersTable
        controllers={[controller]}
        isPending={false}
        rowSelection={{}}
        setRowSelection={vi.fn()}
      />,
      { state }
    );

    expect(screen.getAllByRole("link")[0]).toHaveAttribute(
      "href",
      urls.controllers.controller.index({
        id: controller.system_id,
      })
    );
  });

  describe("sorting", () => {
    it("can sort by FQDN", async () => {
      const controllers = [
        factory.controller({
          fqdn: "lion",
          system_id: "lion",
          hostname: "lion",
        }),
        factory.controller({
          fqdn: "zebra",
          system_id: "zebra",
          hostname: "zebra",
        }),
        factory.controller({
          fqdn: "anaconda",
          system_id: "anaconda",
          hostname: "anaconda",
        }),
      ];
      state.controller.items = controllers;
      renderWithProviders(
        <ControllersTable
          controllers={controllers}
          isPending={false}
          rowSelection={{}}
          setRowSelection={vi.fn()}
        />,
        { state }
      );

      await waitForLoading();

      let rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");

      expect(within(rows[0]).getAllByRole("cell")[1]).toHaveTextContent(
        /anaconda/i
      );
      expect(within(rows[1]).getAllByRole("cell")[1]).toHaveTextContent(
        /lion/i
      );
      expect(within(rows[2]).getAllByRole("cell")[1]).toHaveTextContent(
        /zebra/i
      );

      // Change sort to ascending FQDN
      await userEvent.click(screen.getByRole("button", { name: /name/i }));

      rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");

      expect(within(rows[0]).getAllByRole("cell")[1]).toHaveTextContent(
        /zebra/i
      );
      expect(within(rows[1]).getAllByRole("cell")[1]).toHaveTextContent(
        /lion/i
      );
      expect(within(rows[2]).getAllByRole("cell")[1]).toHaveTextContent(
        /anaconda/i
      );
    });
  });

  describe("vault status icons", () => {
    it("shows no icons by default", () => {
      const controllers = [
        factory.controller({ system_id: "abc123" }),
        factory.controller({ system_id: "def456" }),
      ];
      state.controller.items = controllers;
      renderWithProviders(
        <ControllersTable
          controllers={controllers}
          isPending={false}
          rowSelection={{}}
          setRowSelection={vi.fn()}
        />,
        { state }
      );

      expect(screen.queryByTestId("vault-icon")).not.toBeInTheDocument();
    });

    it("shows icons with appropriate tooltips based on vault status for each controller", async () => {
      const controllers = [
        factory.controller({
          system_id: "abc123",
          vault_configured: true,
          node_type: NodeType.REGION_CONTROLLER,
        }),
        factory.controller({
          system_id: "def456",
          vault_configured: false,
          node_type: NodeType.REGION_AND_RACK_CONTROLLER,
        }),
      ];
      state.controller.items = controllers;

      renderWithProviders(
        <ControllersTable
          controllers={controllers}
          isPending={false}
          rowSelection={{}}
          setRowSelection={vi.fn()}
        />,
        { state }
      );

      const rows = screen.getAllByRole("row");

      expect(within(rows[1]).getByTestId("vault-icon")).toHaveClass(
        "p-icon--security"
      );
      await userEvent.click(
        within(rows[1]).getByRole("button", { name: /security/i })
      );
      expect(
        within(rows[1]).getByTestId("vault-icon")
      ).toHaveAccessibleDescription(
        "Vault is configured on this controller. Once all controllers are configured, migrate the secrets. Read more about Vault integration"
      );
      expect(
        screen.getByRole("tooltip", {
          name: "Vault is configured on this controller. Once all controllers are configured, migrate the secrets. Read more about Vault integration",
        })
      ).toBeInTheDocument();

      expect(within(rows[2]).getByTestId("vault-icon")).toHaveClass(
        "p-icon--security-warning"
      );
      await userEvent.click(within(rows[2]).getByRole("button"));
      expect(
        within(rows[2]).getByTestId("vault-icon")
      ).toHaveAccessibleDescription(
        "Missing Vault configuration. Read more about Vault integration"
      );
      expect(
        screen.getByRole("tooltip", {
          name: "Missing Vault configuration. Read more about Vault integration",
        })
      ).toBeInTheDocument();
    });

    it("displays a security-tick with appropriate tooltip on controllers once they are all configured and vault is enabled", async () => {
      const controllers = [
        factory.controller({
          system_id: "abc123",
          vault_configured: true,
          node_type: NodeType.REGION_CONTROLLER,
        }),
        factory.controller({
          system_id: "def456",
          vault_configured: true,
          node_type: NodeType.REGION_AND_RACK_CONTROLLER,
        }),
      ];
      state.controller.items = controllers;
      state.general = factory.generalState({
        vaultEnabled: factory.vaultEnabledState({
          data: true,
          loaded: true,
        }),
      });

      renderWithProviders(
        <ControllersTable
          controllers={controllers}
          isPending={false}
          rowSelection={{}}
          setRowSelection={vi.fn()}
        />,
        { state }
      );

      const rows = screen.getAllByRole("row");
      await userEvent.click(
        screen.getAllByRole("button", { name: /security/i })[0]
      );
      expect(
        screen.getAllByRole("tooltip", {
          name: "Vault is configured on this region controller for secret storage. Read more about Vault integration",
        })[0]
      ).toBeInTheDocument();
      expect(within(rows[1]).getByTestId("vault-icon")).toHaveClass(
        "p-icon--security-tick"
      );
      expect(within(rows[2]).getByTestId("vault-icon")).toHaveClass(
        "p-icon--security-tick"
      );
    });

    it("does not show vault icons on rack controllers", () => {
      const controllers = [
        factory.controller({
          system_id: "abc123",
          vault_configured: true,
          node_type: NodeType.REGION_CONTROLLER,
        }),
        factory.controller({
          system_id: "def456",
          vault_configured: true,
          node_type: NodeType.REGION_AND_RACK_CONTROLLER,
        }),
        factory.controller({
          system_id: "ghi789",
          vault_configured: true,
          node_type: NodeType.RACK_CONTROLLER,
        }),
      ];
      state.controller.items = controllers;
      state.general = factory.generalState({
        vaultEnabled: factory.vaultEnabledState({
          data: true,
          loaded: true,
        }),
      });

      renderWithProviders(
        <ControllersTable
          controllers={controllers}
          isPending={false}
          rowSelection={{}}
          setRowSelection={vi.fn()}
        />,
        { state }
      );

      const rows = screen.getAllByRole("row");
      expect(within(rows[1]).getByTestId("vault-icon")).toHaveClass(
        "p-icon--security-tick"
      );

      expect(within(rows[2]).getByTestId("vault-icon")).toHaveClass(
        "p-icon--security-tick"
      );

      expect(
        within(rows[3]).queryByTestId("vault-icon")
      ).not.toBeInTheDocument();
    });
  });

  it("displays message for empty state", () => {
    renderWithProviders(
      <ControllersTable
        controllers={[]}
        isPending={false}
        rowSelection={{}}
        setRowSelection={vi.fn()}
      />,
      { state }
    );

    expect(screen.getByText(/No controllers available./i)).toBeInTheDocument();
  });
});
