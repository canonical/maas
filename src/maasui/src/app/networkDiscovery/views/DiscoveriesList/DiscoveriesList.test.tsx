import { waitFor } from "@testing-library/react";

import DiscoveriesList from "./DiscoveriesList";

import { authResolvers } from "@/testing/resolvers/auth";
import { networkDiscoveryResolvers } from "@/testing/resolvers/networkDiscovery";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
} from "@/testing/utils";

setupMockServer(
  networkDiscoveryResolvers.listNetworkDiscoveries.handler(),
  authResolvers.getCurrentUser.handler(),
  authResolvers.getMeStatistics.handler()
);

describe("DiscoveriesList", () => {
  it("renders AddDiscovery when a valid discovery is provided", async () => {
    renderWithProviders(<DiscoveriesList />);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Toggle menu" }));
    });
    await userEvent.click(
      screen.getAllByRole("button", { name: "Toggle menu" })[0]
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Add discovery..." })
    );
    await waitFor(() => {
      expect(
        screen.getByRole("complementary", { name: "Add discovery" })
      ).toBeInTheDocument();
    });
  });

  it("renders DeleteDiscovery when a valid discovery is provided", async () => {
    renderWithProviders(<DiscoveriesList />);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Toggle menu" }));
    });
    await userEvent.click(
      screen.getAllByRole("button", { name: "Toggle menu" })[0]
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Delete discovery..." })
    );
    await waitFor(() => {
      expect(
        screen.getByRole("complementary", { name: "Delete discovery" })
      ).toBeInTheDocument();
    });
  });

  it("renders ClearAllForm", async () => {
    renderWithProviders(<DiscoveriesList />);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Clear all discoveries" }));
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Clear all discoveries" })
    );
    await waitFor(() => {
      expect(
        screen.getByRole("complementary", { name: "Clear all discoveries" })
      ).toBeInTheDocument();
    });
  });

  it("closes side panel form when canceled", async () => {
    renderWithProviders(<DiscoveriesList />);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Clear all discoveries" }));
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Clear all discoveries" })
    );
    await waitFor(() => {
      expect(
        screen.getByRole("complementary", { name: "Clear all discoveries" })
      ).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.queryByRole("complementary", { name: "Clear all discoveries" })
    ).not.toBeInTheDocument();
  });
});
