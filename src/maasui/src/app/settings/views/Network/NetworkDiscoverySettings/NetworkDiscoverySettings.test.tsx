import { waitFor } from "@testing-library/react";

import NetworkDiscoverySettings from "@/app/settings/views/Network/NetworkDiscoverySettings/NetworkDiscoverySettings";
import { ConfigNames } from "@/app/store/config/types";
import * as factory from "@/testing/factories";
import { authResolvers, mockAuth } from "@/testing/resolvers/auth";
import { networkDiscoveryResolvers } from "@/testing/resolvers/networkDiscovery";
import { renderWithProviders, screen, setupMockServer } from "@/testing/utils";

const mockServer = setupMockServer(
  networkDiscoveryResolvers.listNetworkDiscoveries.handler(),
  authResolvers.getCurrentUser.handler({ ...mockAuth, is_superuser: true }),
  authResolvers.getMeStatistics.handler()
);

describe("NetworkDiscoverySettings", () => {
  it("renders permission message if user is not superuser", async () => {
    mockServer.use(
      authResolvers.getCurrentUser.handler({ ...mockAuth, is_superuser: false })
    );
    renderWithProviders(<NetworkDiscoverySettings />);
    await waitFor(() => {
      expect(
        screen.getByText("You do not have permission to view this page.")
      ).toBeInTheDocument();
    });
  });

  it("shows disabled discovery warning", async () => {
    const state = factory.rootState({
      config: factory.configState({
        items: [
          {
            name: ConfigNames.NETWORK_DISCOVERY,
            value: "disabled",
          },
        ],
        loaded: true,
      }),
    });
    renderWithProviders(<NetworkDiscoverySettings />, { state });
    await waitFor(() => {
      expect(
        screen.getByText(
          "List of devices will not update as discovery is turned off."
        )
      ).toBeInTheDocument();
    });
  });
});
