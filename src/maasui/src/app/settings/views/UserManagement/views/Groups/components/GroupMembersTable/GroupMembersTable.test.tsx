import GroupMembersTable from "./GroupMembersTable";

import RemoveGroupMember from "@/app/settings/views/UserManagement/views/Groups/components/RemoveGroupMember";
import { groupsResolvers, mockGroupMembers } from "@/testing/resolvers/groups";
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

const mockServer = setupMockServer(groupsResolvers.listGroupMembers.handler());

describe("GroupMembersTable", () => {
  describe("display", () => {
    it("displays a loading component if members are loading", async () => {
      mockIsPending();
      renderWithProviders(
        <GroupMembersTable
          id={1}
          memberSelection={[]}
          setMemberSelection={vi.fn}
        />
      );

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      mockServer.use(
        groupsResolvers.listGroupMembers.handler({ items: [], total: 0 })
      );
      renderWithProviders(
        <GroupMembersTable
          id={1}
          memberSelection={[]}
          setMemberSelection={vi.fn}
        />
      );

      await waitFor(() => {
        expect(screen.getByText("No group members found.")).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(
        <GroupMembersTable
          id={1}
          memberSelection={[]}
          setMemberSelection={vi.fn}
        />
      );

      ["Username", "Email", "Actions"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });
  });

  describe("selection", () => {
    it("calls setMemberSelection with the correct member when a row is checked", async () => {
      const setMemberSelection = vi.fn();

      renderWithProviders(
        <GroupMembersTable
          id={1}
          memberSelection={[]}
          setMemberSelection={setMemberSelection}
        />
      );

      await waitFor(() => {
        expect(screen.getAllByRole("checkbox").length).toBeGreaterThan(0);
      });

      const [, firstRowCheckbox] = screen.getAllByRole("checkbox");
      await userEvent.click(firstRowCheckbox);

      expect(setMemberSelection).toHaveBeenCalled();
    });
  });

  describe("actions", () => {
    it("opens the RemoveGroupMember side panel when clicking Remove member", async () => {
      renderWithProviders(
        <GroupMembersTable
          id={1}
          memberSelection={[]}
          setMemberSelection={vi.fn}
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
        screen.getByRole("button", { name: "Remove member..." })
      );

      const selectedMember = mockGroupMembers.items[0];
      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: RemoveGroupMember,
          title: "Remove member",
          props: expect.objectContaining({
            groupId: 1,
            members: [selectedMember],
          }),
        })
      );
    });
  });
});
