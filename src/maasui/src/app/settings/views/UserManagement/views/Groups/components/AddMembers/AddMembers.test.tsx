import AddMembers from "./AddMembers";

import { groupsResolvers, mockGroupMembers } from "@/testing/resolvers/groups";
import { mockUsers, usersResolvers } from "@/testing/resolvers/users";
import {
  userEvent,
  screen,
  setupMockServer,
  renderWithProviders,
  waitFor,
  waitForLoading,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  groupsResolvers.listGroupMembers.handler(),
  groupsResolvers.addGroupMember.handler(),
  usersResolvers.listUsers.handler()
);
const { mockClose } = await mockSidePanel();

describe("AddMembers", () => {
  it("closes the side panel when the cancel button is clicked", async () => {
    renderWithProviders(<AddMembers groupId={1} />);

    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));

    expect(mockClose).toHaveBeenCalled();
  });

  it("renders the users table with username and email columns", async () => {
    renderWithProviders(<AddMembers groupId={1} />);

    await waitForLoading();

    expect(
      screen.getByRole("columnheader", { name: /username/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: /email/i })
    ).toBeInTheDocument();
  });

  it("pre-selects existing group members as disabled rows", async () => {
    renderWithProviders(<AddMembers groupId={1} />);

    await waitForLoading();

    const checkboxes = screen.getAllByRole("checkbox");
    const checkedBoxes = checkboxes.filter(
      (cb) => (cb as HTMLInputElement).checked
    );
    expect(checkedBoxes.length).toBe(mockGroupMembers.items.length);
  });

  it("calls add group members on save click", async () => {
    renderWithProviders(<AddMembers groupId={1} />);

    await waitFor(() => {
      expect(screen.getByText(mockUsers.items[2].username)).toBeInTheDocument();
    });

    // user3 (id: 3) is not an existing member — find its unchecked, enabled checkbox
    const user3Checkbox = screen
      .getAllByRole("checkbox")
      .find(
        (cb) =>
          !(cb as HTMLInputElement).disabled &&
          !(cb as HTMLInputElement).checked
      );
    expect(user3Checkbox).toBeDefined();
    await userEvent.click(user3Checkbox!);

    await userEvent.click(
      screen.getByRole("button", { name: /Add 1 member/i })
    );

    await waitFor(() => {
      expect(groupsResolvers.addGroupMember.resolved).toBeTruthy();
    });
  });

  it("displays an error message when adding members fails", async () => {
    mockServer.use(
      groupsResolvers.addGroupMember.error({
        code: 400,
        message: "Failed to add members.",
      })
    );

    renderWithProviders(<AddMembers groupId={1} />);

    await waitFor(() => {
      expect(screen.getByText(mockUsers.items[2].username)).toBeInTheDocument();
    });

    const user3Checkbox = screen
      .getAllByRole("checkbox")
      .find(
        (cb) =>
          !(cb as HTMLInputElement).disabled &&
          !(cb as HTMLInputElement).checked
      );
    await userEvent.click(user3Checkbox!);

    await userEvent.click(
      screen.getByRole("button", { name: /Add 1 member/i })
    );

    await waitFor(() => {
      expect(screen.getByText("Failed to add members.")).toBeInTheDocument();
    });
  });

  it("filters users by search text", async () => {
    renderWithProviders(<AddMembers groupId={1} />);

    await waitForLoading();

    const searchBox = screen.getByPlaceholderText("Search users");
    await userEvent.type(searchBox, "user3");

    await waitFor(() => {
      expect(usersResolvers.listUsers.resolved).toBeTruthy();
    });
  });

  it("disables the submit button when no new members are selected", async () => {
    renderWithProviders(<AddMembers groupId={1} />);

    await waitForLoading();

    // All users from mockUsers (ids 1 & 2) are already members — no new selection possible
    expect(
      screen.getByRole("button", { name: /Add 0 members/i })
    ).toBeDisabled();
  });

  it("closes the side panel on successful add", async () => {
    renderWithProviders(<AddMembers groupId={1} />);

    await waitFor(() => {
      expect(screen.getByText(mockUsers.items[2].username)).toBeInTheDocument();
    });

    const user3Checkbox = screen
      .getAllByRole("checkbox")
      .find(
        (cb) =>
          !(cb as HTMLInputElement).disabled &&
          !(cb as HTMLInputElement).checked
      );
    await userEvent.click(user3Checkbox!);

    await userEvent.click(
      screen.getByRole("button", { name: /Add 1 member/i })
    );

    await waitFor(() => {
      expect(mockClose).toHaveBeenCalled();
    });
  });
});
