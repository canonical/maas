import VaultNotification from "./VaultNotification";

import { NodeType } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

it("does not display a notification when data has not loaded", async () => {
  const state = factory.rootState();
  state.controller.loaded = false;
  renderWithProviders(<VaultNotification />, {
    state,
  });
  expect(
    screen.queryByText(/Incomplete Vault integration/)
  ).not.toBeInTheDocument();
});

it("displays a notification when data has loaded and not all controllers are configured", async () => {
  const state = factory.rootState();
  state.controller.loaded = true;
  state.general.vaultEnabled.loaded = true;
  state.general.vaultEnabled.data = false;
  state.controller.items = [
    factory.controller({
      vault_configured: false,
      node_type: NodeType.REGION_AND_RACK_CONTROLLER,
    }),
    factory.controller({
      vault_configured: true,
      node_type: NodeType.REGION_CONTROLLER,
    }),
  ];
  renderWithProviders(<VaultNotification />, {
    state,
  });
  expect(screen.getByText(/Incomplete Vault integration/)).toBeInTheDocument();
});

it("displays a notification when data has loaded and secrets are not migrated to Vault", async () => {
  const state = factory.rootState();
  state.controller.loaded = true;
  state.general.vaultEnabled.loaded = true;
  state.general.vaultEnabled.data = false;
  state.controller.items = [
    factory.controller({
      vault_configured: true,
      node_type: NodeType.REGION_AND_RACK_CONTROLLER,
    }),
    factory.controller({
      vault_configured: true,
      node_type: NodeType.REGION_CONTROLLER,
    }),
  ];
  renderWithProviders(<VaultNotification />, {
    state,
  });
  expect(screen.getByText(/Incomplete Vault integration/)).toBeInTheDocument();
});

it("doesn't display a notification if vault setup is complete", async () => {
  const state = factory.rootState();
  state.controller.loaded = true;
  state.general.vaultEnabled.loaded = true;
  state.general.vaultEnabled.data = true;
  state.controller.items = [
    factory.controller({
      vault_configured: true,
      node_type: NodeType.REGION_AND_RACK_CONTROLLER,
    }),
    factory.controller({
      vault_configured: true,
      node_type: NodeType.REGION_CONTROLLER,
    }),
  ];
  renderWithProviders(<VaultNotification />, {
    state,
  });
  expect(
    screen.queryByText(/Incomplete Vault integration/)
  ).not.toBeInTheDocument();
});

it("doesn't display a notification if vault setup has not been started", async () => {
  const state = factory.rootState();
  state.controller.loaded = true;
  state.general.vaultEnabled.loaded = true;
  state.general.vaultEnabled.data = false;
  state.controller.items = [
    factory.controller({
      vault_configured: false,
      node_type: NodeType.REGION_AND_RACK_CONTROLLER,
    }),
    factory.controller({
      vault_configured: false,
      node_type: NodeType.REGION_CONTROLLER,
    }),
  ];
  renderWithProviders(<VaultNotification />, {
    state,
  });
  expect(
    screen.queryByText(/Incomplete Vault integration/)
  ).not.toBeInTheDocument();
});
