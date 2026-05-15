import userEvent from "@testing-library/user-event";
import { describe } from "vitest";

import DiscoveriesTable from "./DiscoveriesTable";

import {
  DiscoveryAddForm,
  DiscoveryDeleteForm,
} from "@/app/networkDiscovery/components";
import { Labels } from "@/app/networkDiscovery/views/DiscoveriesList/DiscoveriesList";
import { discovery } from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import { networkDiscoveryResolvers } from "@/testing/resolvers/networkDiscovery";
import {
  renderWithProviders,
  screen,
  waitFor,
  setupMockServer,
  mockIsPending,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  networkDiscoveryResolvers.listNetworkDiscoveries.handler(),
  authResolvers.getCurrentUser.handler()
);
const { mockOpen } = await mockSidePanel();

describe("DiscoveriesTable", () => {
  describe("display", () => {
    it("displays a loading component if discoveries are loading", async () => {
      mockIsPending();
      renderWithProviders(<DiscoveriesTable />);

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      mockServer.use(
        networkDiscoveryResolvers.listNetworkDiscoveries.handler({
          items: [],
          total: 0,
        })
      );
      renderWithProviders(<DiscoveriesTable />);

      await waitFor(() => {
        expect(
          screen.getByText("No discoveries available.")
        ).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<DiscoveriesTable />);

      ["Name", "Mac address", "IP", "Last seen", "Action"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });

    it("displays MAC address with organization", async () => {
      const mockDiscovery = discovery({
        id: 1,
        mac_address: "aa:bb:cc:dd:ee:ff",
        mac_organization: "Intel Corporate",
      });
      mockServer.use(
        networkDiscoveryResolvers.listNetworkDiscoveries.handler({
          items: [mockDiscovery],
          total: 1,
        })
      );

      renderWithProviders(<DiscoveriesTable />);

      await waitFor(() => {
        expect(screen.getByText("aa:bb:cc:dd:ee:ff")).toBeInTheDocument();
        expect(screen.getByText("Intel Corporate")).toBeInTheDocument();
      });
    });

    it("displays 'Unknown' when MAC organization is not available", async () => {
      const mockDiscovery = discovery({
        id: 1,
        mac_address: "aa:bb:cc:dd:ee:ff",
        mac_organization: undefined,
      });
      mockServer.use(
        networkDiscoveryResolvers.listNetworkDiscoveries.handler({
          items: [mockDiscovery],
          total: 1,
        })
      );

      renderWithProviders(<DiscoveriesTable />);

      await waitFor(() => {
        expect(screen.getByText("aa:bb:cc:dd:ee:ff")).toBeInTheDocument();
        expect(screen.getByText("Unknown")).toBeInTheDocument();
      });
    });
  });

  describe("actions", () => {
    it("opens add discovery side panel form", async () => {
      const mockDiscovery = discovery({ id: 1 });
      mockServer.use(
        networkDiscoveryResolvers.listNetworkDiscoveries.handler({
          items: [mockDiscovery],
          total: 1,
        })
      );

      renderWithProviders(<DiscoveriesTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Toggle menu" })
        ).toBeInTheDocument();
      });

      await userEvent.click(
        screen.getByRole("button", { name: "Toggle menu" })
      );

      await userEvent.click(
        screen.getByRole("button", { name: Labels.AddDiscovery })
      );

      await waitFor(() => {
        expect(mockOpen).toHaveBeenCalledWith({
          component: DiscoveryAddForm,
          title: "Add discovery",
          props: { discovery: mockDiscovery },
        });
      });
    });

    it("opens delete discovery side panel form", async () => {
      const mockDiscovery = discovery({ id: 1 });
      mockServer.use(
        networkDiscoveryResolvers.listNetworkDiscoveries.handler({
          items: [mockDiscovery],
          total: 1,
        })
      );

      renderWithProviders(<DiscoveriesTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Toggle menu" })
        ).toBeInTheDocument();
      });

      await userEvent.click(
        screen.getByRole("button", { name: "Toggle menu" })
      );

      await userEvent.click(
        screen.getByRole("button", { name: Labels.DeleteDiscovery })
      );

      await waitFor(() => {
        expect(mockOpen).toHaveBeenCalledWith({
          component: DiscoveryDeleteForm,
          title: "Delete discovery",
          props: { discovery: mockDiscovery },
        });
      });
    });
  });
});
