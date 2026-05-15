import SingleSignOn from "./SingleSignOn";
import ResetSingleSignOn from "./components/ResetSingleSignOn";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
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
  authResolvers.getActiveOauthProvider.handler()
);

const { mockOpen } = await mockSidePanel();

describe("Single sign-on", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      general: factory.generalState({
        maasURL: {
          data: "http://example.com/maas",
          errors: null,
          loaded: true,
          loading: false,
        },
      }),
    });
  });

  it("displays a spinner while loading provider information", async () => {
    mockIsPending();

    renderWithProviders(<SingleSignOn />, { state });

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("displays a pre-filled form when provider data loads", async () => {
    renderWithProviders(<SingleSignOn />, { state });

    await waitFor(() => {
      expect(
        screen.getByRole("form", { name: "Single sign-on form" })
      ).toBeInTheDocument();
    });

    expect(screen.getByRole("textbox", { name: /Name/i })).toHaveValue(
      mockOauthProvider.name
    );
  });

  it("displays an empty form if no provider is found", async () => {
    mockServer.use(
      authResolvers.getActiveOauthProvider.error({
        message: "Not found",
        code: 404,
        kind: "Error",
      })
    );

    renderWithProviders(<SingleSignOn />, { state });

    await waitFor(() => {
      expect(
        screen.getByRole("form", { name: "Single sign-on form" })
      ).toBeInTheDocument();
    });

    expect(screen.queryByText(/Error/)).not.toBeInTheDocument();

    expect(screen.getByRole("textbox", { name: /Name/i })).toHaveValue("");
  });

  it("displays an error message for other kinds of errors", async () => {
    mockServer.use(
      authResolvers.getActiveOauthProvider.error({
        message: "Internal server error",
        code: 500,
        kind: "Error",
      })
    );

    renderWithProviders(<SingleSignOn />, { state });

    await waitFor(() => {
      expect(
        screen.getByText("Error while fetching OIDC provider")
      ).toBeInTheDocument();
    });

    expect(screen.getByText("Internal server error")).toBeInTheDocument();
  });

  it("disables the 'Reset' button and shows a tooltip when no OIDC configuration exists", async () => {
    mockServer.use(
      authResolvers.getActiveOauthProvider.error({
        message: "Not found",
        code: 404,
        kind: "Error",
      })
    );

    renderWithProviders(<SingleSignOn />, { state });

    await waitFor(() => {
      expect(
        screen.getByRole("form", { name: "Single sign-on form" })
      ).toBeInTheDocument();
    });

    const resetButton = screen.getByRole("button", { name: /Reset/i });

    expect(resetButton).toBeAriaDisabled();

    await userEvent.hover(resetButton);

    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent(
        "No single sign-on provider is configured."
      );
    });
  });

  it("enables the 'Reset' button and does not show a tooltip when OIDC is configured", async () => {
    renderWithProviders(<SingleSignOn />, { state });

    await waitFor(() => {
      expect(
        screen.getByRole("form", { name: "Single sign-on form" })
      ).toBeInTheDocument();
    });

    const resetButton = screen.getByRole("button", { name: /Reset/i });

    expect(resetButton).not.toBeAriaDisabled();

    await userEvent.hover(resetButton);

    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    });
  });

  it("opens the side panel when 'Reset' is clicked", async () => {
    renderWithProviders(<SingleSignOn />, { state });

    await waitFor(() => {
      expect(
        screen.getByRole("form", { name: "Single sign-on form" })
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: /Reset/i }));

    expect(mockOpen).toHaveBeenCalledWith({
      component: ResetSingleSignOn,
      title: "Reset OIDC configuration",
      props: {
        id: mockOauthProvider.id,
      },
    });
  });
});
