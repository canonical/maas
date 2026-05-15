import RemoveGroupMember from "./RemoveGroupMember";

import { groupsResolvers, mockGroupMembers } from "@/testing/resolvers/groups";
import {
  userEvent,
  screen,
  setupMockServer,
  renderWithProviders,
  waitFor,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(groupsResolvers.removeGroupMember.handler());
const { mockClose } = await mockSidePanel();

describe("RemoveGroupMember", () => {
  it("closes the side panel when the cancel button is clicked", async () => {
    renderWithProviders(
      <RemoveGroupMember
        groupId={1}
        members={mockGroupMembers.items}
        setMemberSelection={vi.fn}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls remove member on confirm click", async () => {
    renderWithProviders(
      <RemoveGroupMember
        groupId={1}
        members={mockGroupMembers.items}
        setMemberSelection={vi.fn}
      />
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Remove 2 members/i })
    );

    await waitFor(() => {
      expect(groupsResolvers.removeGroupMember.resolved).toBeTruthy();
    });
  });

  it("displays error message when remove member fails", async () => {
    mockServer.use(
      groupsResolvers.removeGroupMember.error({
        code: 400,
        message: "Uh oh!",
        kind: "Error",
      })
    );

    renderWithProviders(
      <RemoveGroupMember
        groupId={1}
        members={mockGroupMembers.items}
        setMemberSelection={vi.fn}
      />
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Remove 2 members/i })
    );

    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });

  it("lists each member with their email in the confirmation message", () => {
    renderWithProviders(
      <RemoveGroupMember
        groupId={1}
        members={mockGroupMembers.items}
        setMemberSelection={vi.fn}
      />
    );

    mockGroupMembers.items.forEach(({ username, email }) => {
      expect(screen.getByText(`${username} (${email})`)).toBeInTheDocument();
    });
  });

  it("uses singular label when removing a single member", () => {
    renderWithProviders(
      <RemoveGroupMember
        groupId={1}
        members={[mockGroupMembers.items[0]]}
        setMemberSelection={vi.fn}
      />
    );

    expect(
      screen.getByRole("button", { name: "Remove 1 member" })
    ).toBeInTheDocument();
  });

  it("closes the side panel on successful removal", async () => {
    renderWithProviders(
      <RemoveGroupMember
        groupId={1}
        members={mockGroupMembers.items}
        setMemberSelection={vi.fn}
      />
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Remove 2 members/i })
    );

    await waitFor(() => {
      expect(mockClose).toHaveBeenCalled();
    });
  });
});
