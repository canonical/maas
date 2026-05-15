import AddEntitlement from "./AddEntitlement";

import {
  Entitlement,
  RestrictableEntitlements,
} from "@/app/settings/views/UserManagement/views/Groups/constants";
import { groupsResolvers } from "@/testing/resolvers/groups";
import { mockPools, poolsResolvers } from "@/testing/resolvers/pools";
import {
  userEvent,
  screen,
  setupMockServer,
  renderWithProviders,
  waitFor,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  groupsResolvers.addGroupEntitlement.handler(),
  poolsResolvers.listPools.handler()
);
const { mockClose } = await mockSidePanel();

describe("AddEntitlement", () => {
  it("runs closeForm function when the cancel button is clicked", async () => {
    renderWithProviders(<AddEntitlement group_id={1} />);

    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls add group entitlement on save click", async () => {
    renderWithProviders(<AddEntitlement group_id={1} />);

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /entitlement/i }),
      Entitlement.CAN_DEPLOY_MACHINES
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Add entitlement/i })
    );

    await waitFor(() => {
      expect(groupsResolvers.addGroupEntitlement.resolved).toBeTruthy();
    });
  });

  it("displays error message when add group entitlement fails", async () => {
    mockServer.use(
      groupsResolvers.addGroupEntitlement.error({
        code: 400,
        message: "Uh oh!",
      })
    );

    renderWithProviders(<AddEntitlement group_id={1} />);

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /entitlement/i }),
      Entitlement.CAN_DEPLOY_MACHINES
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Add entitlement/i })
    );

    await waitFor(() => {
      expect(screen.getByText("Uh oh!")).toBeInTheDocument();
    });
  });

  it("renders conditional fields correctly based on entitlement and pool selection", async () => {
    renderWithProviders(<AddEntitlement group_id={1} />);

    // 1. Entitlement select and is_restricted checkbox are visible
    expect(
      screen.getByRole("combobox", { name: /entitlement/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: /restrict to pool/i })
    ).toBeInTheDocument();

    // 2. is_restricted checkbox and submit button are disabled before entitlement selection
    expect(
      screen.getByRole("checkbox", { name: /restrict to pool/i })
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /Add entitlement/i })
    ).toBeDisabled();

    // 3. Select a restrictable entitlement
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /entitlement/i }),
      RestrictableEntitlements[0]
    );

    // 4. is_restricted checkbox and submit button are now enabled
    expect(
      screen.getByRole("checkbox", { name: /restrict to pool/i })
    ).not.toBeDisabled();
    expect(
      screen.getByRole("button", { name: /Add entitlement/i })
    ).not.toBeDisabled();

    // 5. Check the is_restricted checkbox
    await userEvent.click(
      screen.getByRole("checkbox", { name: /restrict to pool/i })
    );

    // 6. Submit button is disabled (pool not yet selected) and pool select appears
    expect(
      screen.getByRole("button", { name: /Add entitlement/i })
    ).toBeDisabled();
    expect(screen.getByRole("combobox", { name: /pool/i })).toBeInTheDocument();

    // 7. Select a pool — submit button becomes enabled
    await waitFor(() => {
      expect(
        screen.getByRole("combobox", { name: /pool/i })
      ).not.toBeDisabled();
    });
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /pool/i }),
      String(mockPools.items[0].id)
    );
    expect(
      screen.getByRole("button", { name: /Add entitlement/i })
    ).not.toBeDisabled();
  });
});
