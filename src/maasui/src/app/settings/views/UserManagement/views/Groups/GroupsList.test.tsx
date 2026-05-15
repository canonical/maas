import GroupsList from "./GroupsList";

import { groupsResolvers } from "@/testing/resolvers/groups";
import {
  renderWithProviders,
  setupMockServer,
  userEvent,
  screen,
} from "@/testing/utils";

setupMockServer(
  groupsResolvers.listGroups.handler(),
  groupsResolvers.listGroupsStatistics.handler()
);
describe("GroupsList", () => {
  it("renders AddGroup", async () => {
    renderWithProviders(<GroupsList />);
    await userEvent.click(screen.getByRole("button", { name: "Add group" }));
    expect(
      screen.getByRole("complementary", { name: "Add group" })
    ).toBeInTheDocument();
  });
});
