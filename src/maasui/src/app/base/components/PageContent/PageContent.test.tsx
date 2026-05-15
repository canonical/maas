import PageContent from "./PageContent";

import { preferencesNavItems } from "@/app/preferences/constants";
import { settingsNavItems } from "@/app/settings/constants";
import { getTestState, renderWithProviders, screen } from "@/testing/utils";

const state = getTestState();

it("shows the secondary navigation for settings", () => {
  state.status.authenticated = true;
  state.status.connected = true;
  renderWithProviders(<PageContent header="Settings">content</PageContent>, {
    state,
    initialEntries: ["/settings/configuration/general"],
  });

  expect(screen.getByRole("navigation")).toBeInTheDocument();

  settingsNavItems.forEach((item) => {
    expect(screen.getByText(item.label)).toBeInTheDocument();
  });
});

it("shows the secondary navigation for preferences", () => {
  state.status.authenticated = true;
  state.status.connected = true;
  renderWithProviders(<PageContent header="Preferences">content</PageContent>, {
    state,
    initialEntries: ["/account/prefs/details"],
  });

  expect(screen.getByRole("navigation")).toBeInTheDocument();

  preferencesNavItems.forEach((item) => {
    expect(screen.getByText(item.label)).toBeInTheDocument();
  });
});

it("doesn't show the side nav if not authenticated", () => {
  state.status.authenticated = false;
  state.status.connected = true;
  renderWithProviders(<PageContent header="Preferences">content</PageContent>, {
    state,
  });

  expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
});

it("doesn't show the side nav if not connected", () => {
  state.status.authenticated = true;
  state.status.connected = false;
  renderWithProviders(<PageContent header="Preferences">content</PageContent>, {
    state,
  });

  expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
});
