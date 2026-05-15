import { describe } from "vitest";

import LXDHostsTable from "@/app/kvm/views/KVMList/LXDHostsTable/LXDHostsTable";
import { PodType } from "@/app/store/pod/constants";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  zoneResolvers.listZones.handler(),
  zoneResolvers.listZonesWithStatistics.handler(),
  zoneResolvers.getZone.handler(),
  poolsResolvers.getPool.handler()
);

describe("LXDHostsTable", () => {
  describe("display", () => {
    it("displays a loading component if pools are loading", async () => {
      const state = factory.rootState({
        pod: factory.podState({
          loading: true,
        }),
      });
      renderWithProviders(<LXDHostsTable />, { state });

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      renderWithProviders(<LXDHostsTable />);

      await waitFor(() => {
        expect(screen.getByText("No hosts available.")).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<LXDHostsTable />);

      [
        "Name Project",
        "KVM host type",
        "VMs",
        "Tags",
        "AZ Resource Pool",
        "CPU cores",
        "RAM",
        "Storage",
      ].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });

    it("can display a single host type", () => {
      const state = factory.rootState({
        pod: factory.podState({
          items: [
            factory.pod({
              type: PodType.LXD,
            }),
          ],
        }),
      });
      renderWithProviders(<LXDHostsTable />, { state });
      expect(screen.getByText("Single host")).toBeInTheDocument();
      expect(screen.queryByRole("hosts-count")).toBeNull();
    });

    it("can display a cluster host type", () => {
      const state = factory.rootState({
        vmcluster: factory.vmClusterState({
          items: [
            factory.vmCluster({
              hosts: [factory.vmHost(), factory.vmHost()],
            }),
          ],
        }),
      });
      renderWithProviders(<LXDHostsTable />, { state });
      expect(screen.getByText("Cluster")).toBeInTheDocument();
      expect(screen.getByTestId("hosts-count")).toHaveTextContent(
        "2 KVM hosts"
      );
    });
  });
});
