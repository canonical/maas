import RemoveGroupEntitlement from "./RemoveGroupEntitlement";

import { groupEntitlements as groupEntitlementsFactory } from "@/testing/factories/groups";
import {
  groupsResolvers,
  mockGroupEntitlements,
} from "@/testing/resolvers/groups";
import {
  userEvent,
  screen,
  setupMockServer,
  renderWithProviders,
  waitFor,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  groupsResolvers.removeGroupEntitlement.handler()
);
const { mockClose } = await mockSidePanel();

describe("RemoveGroupEntitlement", () => {
  it("closes the side panel when the cancel button is clicked", async () => {
    renderWithProviders(
      <RemoveGroupEntitlement
        entitlements={mockGroupEntitlements.items}
        group_id={1}
        setEntitlementSelection={vi.fn}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls remove entitlement on confirm click", async () => {
    renderWithProviders(
      <RemoveGroupEntitlement
        entitlements={mockGroupEntitlements.items}
        group_id={1}
        setEntitlementSelection={vi.fn}
      />
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Remove 2 entitlements/i })
    );

    await waitFor(() => {
      expect(groupsResolvers.removeGroupEntitlement.resolved).toBeTruthy();
    });
  });

  it("displays error message when remove entitlement fails", async () => {
    mockServer.use(
      groupsResolvers.removeGroupEntitlement.error({
        code: 400,
        message: "Uh oh!",
        kind: "Error",
      })
    );

    renderWithProviders(
      <RemoveGroupEntitlement
        entitlements={mockGroupEntitlements.items}
        group_id={1}
        setEntitlementSelection={vi.fn}
      />
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Remove 2 entitlements/i })
    );

    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });

  it("lists each entitlement with its resource type in the confirmation message", () => {
    renderWithProviders(
      <RemoveGroupEntitlement
        entitlements={mockGroupEntitlements.items}
        group_id={1}
        setEntitlementSelection={vi.fn}
      />
    );

    mockGroupEntitlements.items.forEach(({ entitlement, resource_type }) => {
      expect(
        screen.getByText(new RegExp(`${entitlement}.*${resource_type}`))
      ).toBeInTheDocument();
    });
  });

  it("includes the resource_id in the label when it is non-zero", () => {
    const entitlement = groupEntitlementsFactory({
      entitlement: "can_edit_machines",
      resource_id: 5,
      resource_type: "pool",
    });

    renderWithProviders(
      <RemoveGroupEntitlement
        entitlements={[entitlement]}
        group_id={1}
        setEntitlementSelection={vi.fn}
      />
    );

    expect(screen.getByText(/pool: 5/)).toBeInTheDocument();
  });

  it("omits the resource_id when it is zero", () => {
    const entitlement = groupEntitlementsFactory({
      entitlement: "can_edit_machines",
      resource_id: 0,
      resource_type: "maas",
    });

    renderWithProviders(
      <RemoveGroupEntitlement
        entitlements={[entitlement]}
        group_id={1}
        setEntitlementSelection={vi.fn}
      />
    );

    expect(screen.queryByText(/: 0/)).not.toBeInTheDocument();
  });

  it("uses singular label when removing a single entitlement", () => {
    renderWithProviders(
      <RemoveGroupEntitlement
        entitlements={[mockGroupEntitlements.items[0]]}
        group_id={1}
        setEntitlementSelection={vi.fn}
      />
    );

    expect(
      screen.getByRole("button", { name: "Remove 1 entitlement" })
    ).toBeInTheDocument();
  });

  it("closes the side panel on successful removal", async () => {
    renderWithProviders(
      <RemoveGroupEntitlement
        entitlements={mockGroupEntitlements.items}
        group_id={1}
        setEntitlementSelection={vi.fn}
      />
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Remove 2 entitlements/i })
    );

    await waitFor(() => {
      expect(mockClose).toHaveBeenCalled();
    });
  });
});
