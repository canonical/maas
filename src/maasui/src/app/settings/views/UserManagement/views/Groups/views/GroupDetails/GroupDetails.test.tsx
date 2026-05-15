import { Route, Routes } from "react-router";

import GroupDetails from "./GroupDetails";

import urls from "@/app/settings/urls";
import { groupsResolvers } from "@/testing/resolvers/groups";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  groupsResolvers.getGroup.handler(),
  groupsResolvers.listGroupsStatistics.handler(),
  groupsResolvers.listGroupEntitlements.handler(),
  groupsResolvers.listGroupMembers.handler()
);

describe("GroupDetails", () => {
  it("redirects from the index route to the entitlements tab", async () => {
    const { router } = renderWithProviders(
      <Routes>
        <Route
          element={<GroupDetails />}
          path={`${urls.userManagement.group.index(null)}/*`}
        />
      </Routes>,
      { initialEntries: [urls.userManagement.group.index({ id: 1 })] }
    );

    await waitFor(() => {
      expect(router.state.location.pathname).toBe(
        urls.userManagement.group.entitlements({ id: 1 })
      );
    });
  });

  it("renders the members tab content on the members route", async () => {
    renderWithProviders(
      <Routes>
        <Route
          element={<GroupDetails />}
          path={`${urls.userManagement.group.index(null)}/*`}
        />
      </Routes>,
      { initialEntries: [urls.userManagement.group.members({ id: 1 })] }
    );

    await waitFor(() => {
      expect(
        screen.getByRole("columnheader", { name: /username/i })
      ).toBeInTheDocument();
    });
  });
});
