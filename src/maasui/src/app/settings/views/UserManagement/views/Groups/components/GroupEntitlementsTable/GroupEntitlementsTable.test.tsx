import GroupEntitlementsTable from "./GroupEntitlementsTable";

import RemoveGroupEntitlement from "@/app/settings/views/UserManagement/views/Groups/components/RemoveGroupEntitlement";
import {
  groupsResolvers,
  mockGroupEntitlements,
} from "@/testing/resolvers/groups";
import { poolsResolvers } from "@/testing/resolvers/pools";
import {
  renderWithProviders,
  setupMockServer,
  userEvent,
  screen,
  mockIsPending,
  waitFor,
  mockSidePanel,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

const mockServer = setupMockServer(
  groupsResolvers.listGroupEntitlements.handler(),
  poolsResolvers.getPool.handler()
);

describe("GroupEntitlementsTable", () => {
  describe("display", () => {
    it("displays a loading component if entitlements are loading", async () => {
      mockIsPending();
      renderWithProviders(
        <GroupEntitlementsTable
          entitlementSelection={[]}
          id={1}
          setEntitlementSelection={vi.fn}
        />
      );

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      mockServer.use(
        groupsResolvers.listGroupEntitlements.handler({ items: [], total: 0 })
      );
      renderWithProviders(
        <GroupEntitlementsTable
          entitlementSelection={[]}
          id={1}
          setEntitlementSelection={vi.fn}
        />
      );

      await waitFor(() => {
        expect(
          screen.getByText("No group entitlements found.")
        ).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(
        <GroupEntitlementsTable
          entitlementSelection={[]}
          id={1}
          setEntitlementSelection={vi.fn}
        />
      );

      ["Entitlement", "Applies to", "Actions"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });
  });

  describe("selection", () => {
    it("calls setEntitlementSelection with the correct entitlement when a row is checked", async () => {
      const setEntitlementSelection = vi.fn();

      renderWithProviders(
        <GroupEntitlementsTable
          entitlementSelection={[]}
          id={1}
          setEntitlementSelection={setEntitlementSelection}
        />
      );

      await waitFor(() => {
        expect(screen.getAllByRole("checkbox").length).toBeGreaterThan(0);
      });

      const [, firstRowCheckbox] = screen.getAllByRole("checkbox");
      await userEvent.click(firstRowCheckbox);

      expect(setEntitlementSelection).toHaveBeenCalled();
    });
  });

  describe("actions", () => {
    it("opens the RemoveGroupEntitlement side panel when clicking Remove entitlement", async () => {
      renderWithProviders(
        <GroupEntitlementsTable
          entitlementSelection={[]}
          id={1}
          setEntitlementSelection={vi.fn}
        />
      );

      await waitFor(() => {
        expect(
          screen.getAllByRole("button", { name: "Toggle menu" }).length
        ).toBeGreaterThan(0);
      });

      await userEvent.click(
        screen.getAllByRole("button", { name: "Toggle menu" })[0]
      );

      await userEvent.click(
        screen.getByRole("button", { name: "Remove entitlement..." })
      );

      const selectedEntitlement = mockGroupEntitlements.items[0];
      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: RemoveGroupEntitlement,
          title: "Remove entitlement",
          props: expect.objectContaining({
            group_id: 1,
            entitlements: [selectedEntitlement],
          }),
        })
      );
    });
  });
});
