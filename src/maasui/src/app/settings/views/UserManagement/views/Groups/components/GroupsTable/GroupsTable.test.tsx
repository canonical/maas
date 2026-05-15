import AddGroup from "../AddGroup";
import DeleteGroup from "../DeleteGroup";
import EditGroup from "../EditGroup";

import GroupsTable from "./GroupsTable";

import { groupsResolvers } from "@/testing/resolvers/groups";
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
  groupsResolvers.listGroups.handler(),
  groupsResolvers.listGroupsStatistics.handler()
);

describe("GroupsTable", () => {
  describe("display", () => {
    it("displays a loading component if groups are loading", async () => {
      mockIsPending();
      renderWithProviders(<GroupsTable />);

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      mockServer.use(
        groupsResolvers.listGroups.handler({ items: [], total: 0 })
      );
      renderWithProviders(<GroupsTable />);

      await waitFor(() => {
        expect(screen.getByText("No groups found.")).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<GroupsTable />);

      ["Name", "Description", "User count", "Action"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });
  });
  describe("actions", () => {
    it("opens the AddGroup side panel side panel", async () => {
      renderWithProviders(<GroupsTable />);
      await userEvent.click(screen.getByRole("button", { name: "Add group" }));
      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: AddGroup,
          title: "Add group",
        })
      );
    });
    it("opens the EditGroup side panel when clicking edit action", async () => {
      renderWithProviders(<GroupsTable />);
      await waitFor(() => {
        expect(screen.getAllByRole("button", { name: "Edit" }));
      });
      await userEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: EditGroup,
          props: { id: 1 },
          title: "Edit group",
        })
      );
    });
    it("opens the DeleteGroup side panel when clicking delete action", async () => {
      renderWithProviders(<GroupsTable />);
      await waitFor(() => {
        expect(screen.getAllByRole("button", { name: "Delete" }));
      });
      await userEvent.click(
        screen.getAllByRole("button", { name: "Delete" })[0]
      );
      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: DeleteGroup,
          props: { id: 1, user_count: 5 },
          title: "Delete group",
        })
      );
    });
  });
});
