import DeleteGroup from "./DeleteGroup";

import { groupsResolvers } from "@/testing/resolvers/groups";
import {
  userEvent,
  screen,
  setupMockServer,
  renderWithProviders,
  waitFor,
  mockSidePanel,
  waitForLoading,
} from "@/testing/utils";

const mockServer = setupMockServer(
  groupsResolvers.deleteGroup.handler(),
  groupsResolvers.getGroup.handler()
);
const { mockClose } = await mockSidePanel();

describe("DeleteGroup", () => {
  const testGroupId = 1;
  it("runs closeForm function when the cancel button is clicked", async () => {
    renderWithProviders(<DeleteGroup id={testGroupId} user_count={0} />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Cancel" })
      ).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls delete group on confirm click", async () => {
    renderWithProviders(<DeleteGroup id={testGroupId} user_count={0} />);

    await waitFor(() => {
      expect(
        screen.getByText(/Are you sure you want to delete this group\?/)
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: /Delete/i }));

    await waitFor(() => {
      expect(groupsResolvers.deleteGroup.resolved).toBeTruthy();
    });
  });

  it("displays caution notification when group has associated users", async () => {
    renderWithProviders(<DeleteGroup id={testGroupId} user_count={5} />);

    await waitFor(() => {
      expect(
        screen.getByText(/Are you sure you want to delete this group\?/)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/This action will remove permissions for/)
      ).toBeInTheDocument();
      expect(screen.getByText(/5 associated members/)).toBeInTheDocument();
      expect(screen.getByText(/and can not be undone\./)).toBeInTheDocument();
    });
  });

  it("displays error message when delete group fails", async () => {
    mockServer.use(
      groupsResolvers.deleteGroup.error({
        code: 400,
        message: "Uh oh!",
        kind: "DeleteGroupError",
      })
    );

    renderWithProviders(<DeleteGroup id={testGroupId} user_count={0} />);
    await waitForLoading();

    await userEvent.click(screen.getByRole("button", { name: /Delete/i }));

    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
