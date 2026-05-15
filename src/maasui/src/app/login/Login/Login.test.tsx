import Login, { Labels } from "./Login";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

const mockServer = setupMockServer(
  authResolvers.authenticate.handler(),
  authResolvers.createSession.handler(),
  authResolvers.isOidcUser.handler()
);

describe("Login", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      status: factory.statusState({
        externalAuthURL: null,
      }),
    });
  });

  it("can display a login error message", () => {
    state.status.authenticationError = Labels.IncorrectCredentials;
    renderWithProviders(<Login />, { initialEntries: ["/login"], state });
    expect(screen.getByRole("alert")).toHaveTextContent(
      Labels.IncorrectCredentials
    );
  });

  it("can render api login", () => {
    renderWithProviders(<Login />, { initialEntries: ["/login"], state });

    expect(
      screen.getByRole("form", { name: Labels.APILoginForm })
    ).toBeInTheDocument();
  });

  it("can render external login link", () => {
    state.status.externalAuthURL = "http://login.example.com";
    renderWithProviders(<Login />, { initialEntries: ["/login"], state });

    expect(
      screen.getByRole("link", { name: Labels.ExternalLoginButton })
    ).toBeInTheDocument();
  });

  it("hides the password field when a username has not been entered", async () => {
    renderWithProviders(<Login />, { initialEntries: ["/login"], state });

    expect(
      screen.getByRole("textbox", { name: Labels.Username })
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(Labels.Password)).not.toBeInTheDocument();
  });

  it("shows the password field when the user is local", async () => {
    renderWithProviders(<Login />, { initialEntries: ["/login"], state });

    await userEvent.type(
      screen.getByRole("textbox", { name: Labels.Username }),
      "koala"
    );
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(authResolvers.isOidcUser.resolved).toBeTruthy();
      expect(screen.getByLabelText(Labels.Password)).toBeInTheDocument();
    });
  });

  it("can login locally when the user is local", async () => {
    const { store } = renderWithProviders(<Login />, {
      initialEntries: ["/login"],
      state,
    });

    await userEvent.type(
      screen.getByRole("textbox", { name: Labels.Username }),
      "koala"
    );
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(authResolvers.isOidcUser.resolved).toBeTruthy();
      expect(screen.getByLabelText(Labels.Password)).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: Labels.Submit })
      ).toBeInTheDocument();
    });

    await userEvent.type(screen.getByLabelText(Labels.Password), "gumtree");

    await userEvent.click(screen.getByRole("button", { name: Labels.Submit }));

    await waitFor(async () => {
      expect(authResolvers.authenticate.resolved).toBeTruthy();
    });

    expect(
      store.getActions().find((action) => action.type === "status/loginSuccess")
    ).toBeDefined();
  });

  it("can login with external provider when the user is OIDC", async () => {
    mockServer.use(
      authResolvers.isOidcUser.handler({
        is_oidc: true,
        provider_name: "ExampleProvider",
        auth_url: "http://login.provider.com",
      })
    );

    Object.defineProperty(window, "location", {
      value: {
        href: "",
      },
      writable: true,
    });

    renderWithProviders(<Login />, {
      initialEntries: ["/login"],
      state,
    });

    await userEvent.type(
      screen.getByRole("textbox", { name: Labels.Username }),
      "koala"
    );
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(authResolvers.isOidcUser.resolved).toBeTruthy();
      expect(screen.queryByLabelText(Labels.Password)).not.toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Login with ExampleProvider" })
      ).toBeInTheDocument();
      expect(
        screen.getByText("Please sign in with ExampleProvider to continue.")
      ).toBeInTheDocument();
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Login with ExampleProvider" })
    );

    await waitFor(() => {
      expect(window.location.href).toBe("http://login.provider.com");
    });
  });

  it("shows a warning if no users have been added yet", () => {
    state.status.noUsers = true;
    renderWithProviders(<Login />, { initialEntries: ["/login"], state });

    expect(
      screen.getByRole("heading", { name: Labels.NoUsers })
    ).toBeInTheDocument();
  });

  it("shows an error if the provider is misconfigured", async () => {
    state.status.authenticationError = Labels.MissingProviderConfig;
    mockServer.use(authResolvers.isOidcUser.error());
    renderWithProviders(<Login />, { initialEntries: ["/login"], state });

    await userEvent.type(
      screen.getByRole("textbox", { name: Labels.Username }),
      "koala"
    );
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(authResolvers.isOidcUser.resolved).toBeTruthy();
      expect(screen.getByRole("alert")).toHaveTextContent(
        Labels.MissingProviderConfig
      );
    });
  });

  it("redirects to machines after login", async () => {
    const { router } = renderWithProviders(<Login />, {
      initialEntries: ["/login"],
      state,
    });

    await userEvent.type(
      screen.getByRole("textbox", { name: Labels.Username }),
      "koala"
    );
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(authResolvers.isOidcUser.resolved).toBeTruthy();
      expect(screen.getByLabelText(Labels.Password)).toBeInTheDocument();
    });

    await userEvent.type(screen.getByLabelText(Labels.Password), "gumtree");

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Login" })).not.toBeDisabled();
    });

    await userEvent.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => {
      expect(authResolvers.authenticate.resolved).toBeTruthy();
      expect(router.state.location.pathname).toBe("/machines");
    });
  });
});
