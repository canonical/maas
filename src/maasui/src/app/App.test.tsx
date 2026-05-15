import * as reactComponentHooks from "@canonical/react-components/dist/hooks";
import { waitFor } from "@testing-library/react";

import { App } from "./App";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import { statusActions } from "@/app/store/status";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import { notificationResolvers } from "@/testing/resolvers/notifications";
import { renderWithProviders, screen, setupMockServer } from "@/testing/utils";

setupMockServer(
  authResolvers.getCurrentUser.handler(),
  authResolvers.getMeStatistics.handler(),
  authResolvers.createSession.handler(),
  notificationResolvers.listNotifications.handler()
);

vi.mock("@canonical/react-components/dist/hooks", async () => {
  const actual: object = await vi.importActual(
    "@canonical/react-components/dist/hooks"
  );
  return {
    ...actual,
    usePrevious: vi.fn(),
  };
});

describe("App", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [{ name: ConfigNames.COMPLETED_INTRO, value: true }],
      }),
    });
  });

  it("displays correct status on connection errors", () => {
    state.status.error = "Uh oh spaghettio";
    state.status.connectedCount = 2;
    state.status.authenticated = true;
    renderWithProviders(<App />, { initialEntries: ["/settings"], state });
    expect(screen.getByText(/Trying to reconnect/i)).toBeInTheDocument();
  });

  it("displays an error if vault is sealed", async () => {
    state.config.errors = "Vault request failed";
    state.status.authenticated = true;
    state.status.error = null;
    state.status.connected = true;
    renderWithProviders(<App />, { initialEntries: ["/settings"], state });
    await waitFor(() => {
      expect(screen.getByText("Failed to connect")).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        /The server connection failed with the error "Vault request failed"/
      )
    ).toBeInTheDocument();
  });

  it("displays an error if vault is unreachable", async () => {
    state.config.errors = "Vault connection failed";
    state.status.authenticated = true;
    state.status.error = null;
    state.status.connected = true;
    renderWithProviders(<App />, { initialEntries: ["/settings"], state });
    await waitFor(() => {
      expect(screen.getByText("Failed to connect")).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        /The server connection failed with the error "Vault connection failed"/
      )
    ).toBeInTheDocument();
  });

  it("displays a loading message if connecting for the first time", () => {
    state.status.connected = false;
    state.status.connecting = true;
    renderWithProviders(<App />, { initialEntries: ["/settings"], state });
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("does not display a loading message if reconnecting", async () => {
    state.status.connected = true;
    state.status.connecting = true;
    renderWithProviders(<App />, { initialEntries: ["/settings"], state });
    await waitFor(() => {
      expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    });
  });

  it("displays a loading message when authenticating", () => {
    state.status.authenticating = true;
    renderWithProviders(<App />, { initialEntries: ["/settings"], state });
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("connects to the WebSocket", async () => {
    state.status.authenticated = true;

    const { store } = renderWithProviders(<App />, {
      initialEntries: ["/settings"],
      state,
    });
    await waitFor(() => {
      expect(
        store
          .getActions()
          .some((action) => action.type === "status/websocketConnect")
      ).toBe(true);
    });
  });

  it("fetches the auth user when connected", async () => {
    state.status.connected = true;
    state.status.authenticated = true;

    renderWithProviders(<App />, { initialEntries: ["/settings"], state });
    await waitFor(() => {
      expect(authResolvers.getCurrentUser.resolved).toBe(true);
    });
  });

  it("fetches auth details on mount", () => {
    const { store } = renderWithProviders(<App />, {
      initialEntries: ["/settings"],
      state,
    });

    expect(
      store
        .getActions()
        .filter(
          (action) => action.type === statusActions.checkAuthenticated().type
        ).length
    ).toBe(1);
  });

  it("fetches the auth details again when logging out", () => {
    vi.spyOn(reactComponentHooks, "usePrevious").mockReturnValue(true);
    state.status.authenticated = false;

    const { store } = renderWithProviders(<App />, {
      initialEntries: ["/settings"],
      state,
    });

    expect(
      store
        .getActions()
        .filter(
          (action) => action.type === statusActions.checkAuthenticated().type
        ).length
    ).toBe(2);
  });
});
