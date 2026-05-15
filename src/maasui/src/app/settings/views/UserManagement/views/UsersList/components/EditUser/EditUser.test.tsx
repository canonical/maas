import EditUser from "./EditUser";

import { authResolvers } from "@/testing/resolvers/auth";
import { mockUsers, usersResolvers } from "@/testing/resolvers/users";
import {
  userEvent,
  screen,
  waitFor,
  setupMockServer,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  authResolvers.authenticate.handler(),
  usersResolvers.getUser.handler(),
  usersResolvers.updateUser.handler()
);
const { mockClose } = await mockSidePanel();

describe("EditUser", () => {
  const testUserId = 1;

  it("runs closeForm function when the cancel button is clicked", async () => {
    renderWithProviders(<EditUser id={testUserId} />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Cancel" })
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("updates a user on save click", async () => {
    renderWithProviders(<EditUser id={testUserId} />);

    await waitFor(() => {
      expect(screen.getByLabelText("Username")).toBeInTheDocument();
    });

    await userEvent.clear(screen.getByLabelText("Username"));

    await userEvent.type(
      screen.getByRole("textbox", { name: /username/i }),
      "test name 2"
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Change password…/i })
    );

    await userEvent.type(screen.getByLabelText("Password"), "123");

    await userEvent.type(screen.getByLabelText("Password (again)"), "123");

    await userEvent.click(screen.getByRole("button", { name: /Save user/i }));

    await waitFor(() => {
      expect(usersResolvers.updateUser.resolved).toBeTruthy();
    });
  });

  it("updates self-editing user on save click", async () => {
    renderWithProviders(
      <EditUser id={mockUsers.items[0].id} isSelfEditing={true} />
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Username")).toBeInTheDocument();
    });

    await userEvent.clear(screen.getByLabelText("Username"));

    await userEvent.type(
      screen.getByRole("textbox", { name: /username/i }),
      "test name 2"
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Change password…/i })
    );

    await userEvent.type(screen.getByLabelText("Current password"), "111");

    await userEvent.type(screen.getByLabelText("New password"), "123");

    await userEvent.type(screen.getByLabelText("New password (again)"), "123");

    await userEvent.click(
      screen.getByRole("button", { name: /Save profile/i })
    );

    await waitFor(() => {
      expect(usersResolvers.updateUser.resolved).toBeTruthy();
    });
  });

  it("displays authentication error when current password is wrong", async () => {
    mockServer.use(authResolvers.authenticate.error({ code: 401 }));
    renderWithProviders(
      <EditUser id={mockUsers.items[0].id} isSelfEditing={true} />
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Username")).toBeInTheDocument();
    });

    await userEvent.clear(screen.getByLabelText("Username"));

    await userEvent.type(
      screen.getByRole("textbox", { name: /username/i }),
      "test name 2"
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Change password…/i })
    );

    await userEvent.type(screen.getByLabelText("Current password"), "111");

    await userEvent.type(screen.getByLabelText("New password"), "123");

    await userEvent.type(screen.getByLabelText("New password (again)"), "123");

    await userEvent.click(
      screen.getByRole("button", { name: /Save profile/i })
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Current password is incorrect/i)
      ).toBeInTheDocument();
    });
  });

  it("displays error message when update user fails", async () => {
    mockServer.use(
      usersResolvers.updateUser.error({ code: 400, message: "Uh oh!" }),
      usersResolvers.getUser.handler()
    );

    renderWithProviders(<EditUser id={testUserId} />);

    await waitFor(() => {
      expect(screen.getByLabelText("Username")).toBeInTheDocument();
    });

    await userEvent.type(
      screen.getByRole("textbox", { name: /username/i }),
      "test"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save user/i }));

    await waitFor(() => {
      expect(screen.getByText("Uh oh!")).toBeInTheDocument();
    });
  });
});
