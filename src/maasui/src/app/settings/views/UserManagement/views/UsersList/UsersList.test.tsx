import { waitFor } from "@testing-library/react";

import UsersList from "@/app/settings/views/UserManagement/views/UsersList";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import { usersResolvers } from "@/testing/resolvers/users";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
} from "@/testing/utils";

setupMockServer(
  usersResolvers.listUsers.handler(),
  usersResolvers.getUser.handler(),
  authResolvers.getCurrentUser.handler(),
  authResolvers.getMeStatistics.handler()
);

describe("UsersList", () => {
  const state = factory.rootState({
    status: factory.statusState({ externalAuthURL: null }),
  });

  it("renders AddUser", async () => {
    renderWithProviders(<UsersList />, { state });
    await userEvent.click(screen.getByRole("button", { name: "Add user" }));
    expect(
      screen.getByRole("complementary", { name: "Add user" })
    ).toBeInTheDocument();
  });

  it("renders EditUser when a valid userId is provided", async () => {
    renderWithProviders(<UsersList />, { state });
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Edit" }));
    });
    await userEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    expect(
      screen.getByRole("complementary", { name: "Edit user" })
    ).toBeInTheDocument();
  });

  it("renders DeleteUser when a valid userId is provided", async () => {
    renderWithProviders(<UsersList />, { state });
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Delete" }));
    });
    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);
    expect(
      screen.getByRole("complementary", { name: "Delete user" })
    ).toBeInTheDocument();
  });

  it("closes side panel form when canceled", async () => {
    renderWithProviders(<UsersList />, { state });
    await userEvent.click(screen.getByRole("button", { name: "Add user" }));
    expect(
      screen.getByRole("complementary", { name: "Add user" })
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.queryByRole("complementary", { name: "Add user" })
    ).not.toBeInTheDocument();
  });

  it("renders external user maintenance notification", () => {
    renderWithProviders(<UsersList />, {
      state: factory.rootState({
        status: factory.statusState({
          externalAuthURL: "https://external-auth.org",
        }),
      }),
    });
    expect(
      screen.getByText(
        "Users for this MAAS are managed using an external service"
      )
    ).toBeInTheDocument();
  });
});
