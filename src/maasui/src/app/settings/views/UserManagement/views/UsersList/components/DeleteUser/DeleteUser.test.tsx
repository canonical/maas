import DeleteUser from "./DeleteUser";

import { usersResolvers } from "@/testing/resolvers/users";
import {
  userEvent,
  screen,
  setupMockServer,
  waitFor,
  renderWithProviders,
  waitForLoading,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  usersResolvers.getUser.handler(),
  usersResolvers.deleteUser.handler()
);
const { mockClose } = await mockSidePanel();

describe("DeleteUser", () => {
  it("calls closeForm on cancel click", async () => {
    renderWithProviders(<DeleteUser id={2} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls delete user on save click", async () => {
    renderWithProviders(<DeleteUser id={2} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: /Delete/i }));
    await waitFor(() => {
      expect(usersResolvers.deleteUser.resolved).toBeTruthy();
    });
  });

  it("displays error messages when delete user fails", async () => {
    mockServer.use(
      usersResolvers.deleteUser.error({ code: 400, message: "Uh oh!" })
    );

    renderWithProviders(<DeleteUser id={2} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
