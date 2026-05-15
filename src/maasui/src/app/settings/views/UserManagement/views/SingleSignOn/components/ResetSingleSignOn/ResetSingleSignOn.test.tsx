import ResetSingleSignOn from "./ResetSingleSignOn";

import { authResolvers, mockOauthProvider } from "@/testing/resolvers/auth";
import {
  mockIsPending,
  mockSidePanel,
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

const mockServer = setupMockServer(
  authResolvers.updateOauthProvider.handler(),
  authResolvers.deleteOauthProvider.handler(),
  authResolvers.getActiveOauthProvider.handler()
);

const { mockClose } = await mockSidePanel();

describe("ResetSingleSignOn", () => {
  beforeEach(() => {
    authResolvers.updateOauthProvider.resolved = false;
    authResolvers.deleteOauthProvider.resolved = false;
    authResolvers.getActiveOauthProvider.resolved = false;
  });

  it("displays a spinner while loading", () => {
    mockIsPending();

    renderWithProviders(<ResetSingleSignOn id={mockOauthProvider.id} />);

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("shows errors encountered while fetching the provider", async () => {
    mockServer.use(
      authResolvers.getActiveOauthProvider.error({
        message: "Uh oh!",
        code: 500,
        kind: "Error",
      })
    );

    renderWithProviders(<ResetSingleSignOn id={mockOauthProvider.id} />);

    await waitFor(() => {
      expect(
        screen.getByText("Error while fetching OIDC provider")
      ).toBeInTheDocument();
    });

    expect(screen.getByText("Uh oh!")).toBeInTheDocument();
  });

  it("closes the form when 'Cancel' is clicked", async () => {
    renderWithProviders(<ResetSingleSignOn id={mockOauthProvider.id} />);

    await waitFor(() => {
      expect(
        screen.getByRole("form", { name: "Reset single sign-on configuration" })
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(mockClose).toHaveBeenCalled();
  });

  it("updates and deletes the provider, and closes the form when submitted", async () => {
    renderWithProviders(<ResetSingleSignOn id={mockOauthProvider.id} />);

    await waitFor(() => {
      expect(
        screen.getByRole("form", { name: "Reset single sign-on configuration" })
      ).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Reset single sign-on configuration" })
    );

    expect(authResolvers.updateOauthProvider.resolved).toBe(true);
    expect(authResolvers.deleteOauthProvider.resolved).toBe(true);

    expect(mockClose).toHaveBeenCalled();
  });

  it("shows number of users associated with the provider during deletion", async () => {
    mockServer.use(
      authResolvers.getActiveOauthProvider.handler({
        ...mockOauthProvider,
        user_count: 3,
      })
    );

    renderWithProviders(<ResetSingleSignOn id={mockOauthProvider.id} />);

    await waitFor(() => {
      expect(
        screen.getByRole("form", { name: "Reset single sign-on configuration" })
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText("Remove 3 users associated with this provider")
    ).toBeInTheDocument();
  });

  it("doesn't show user removal line if no users are associated with the provider", async () => {
    mockServer.use(
      authResolvers.getActiveOauthProvider.handler({
        ...mockOauthProvider,
        user_count: 0,
      })
    );

    renderWithProviders(<ResetSingleSignOn id={mockOauthProvider.id} />);

    await waitFor(() => {
      expect(
        screen.getByRole("form", { name: "Reset single sign-on configuration" })
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByText(/Remove \d+ users associated with this provider/)
    ).not.toBeInTheDocument();
  });
});
