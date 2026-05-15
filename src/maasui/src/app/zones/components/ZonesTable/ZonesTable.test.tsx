import userEvent from "@testing-library/user-event";
import { describe } from "vitest";

import ZonesTable from "./ZonesTable";

import { DeleteZone, EditZone } from "@/app/zones/components";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  waitFor,
  setupMockServer,
  within,
  mockIsPending,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  zoneResolvers.listZones.handler(),
  zoneResolvers.listZonesWithStatistics.handler(),
  zoneResolvers.getZone.handler(),
  authResolvers.getCurrentUser.handler()
);
const { mockOpen } = await mockSidePanel();

describe("ZonesTable", () => {
  describe("display", () => {
    it("displays a loading component if zones are loading", async () => {
      mockIsPending();
      renderWithProviders(<ZonesTable />);

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      mockServer.use(zoneResolvers.listZones.handler({ items: [], total: 0 }));
      renderWithProviders(<ZonesTable />);

      await waitFor(() => {
        expect(screen.getByText("No zones found.")).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<ZonesTable />);

      [
        "Name",
        "Description",
        "Machines",
        "Devices",
        "Controllers",
        "Actions",
      ].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });

    it("can show a machine filter link", async () => {
      mockServer.use(
        zoneResolvers.listZones.handler({
          items: [
            factory.zone({
              name: "default",
            }),
          ],
          total: 1,
        })
      );

      mockServer.use(
        zoneResolvers.listZonesWithStatistics.handler({
          items: [
            factory.zoneWithStatistics({
              machines_count: 5,
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<ZonesTable />);

      await waitFor(() => {
        expect(
          within(
            screen.getByRole("row", {
              name: new RegExp(`^default`, "i"),
            })
          ).getByRole("link", { name: "5" })
        ).toHaveAttribute("href", "/machines?zone=default");
      });
    });

    it("can show a device filter link", async () => {
      mockServer.use(
        zoneResolvers.listZones.handler({
          items: [
            factory.zone({
              name: "default",
            }),
          ],
          total: 1,
        })
      );

      mockServer.use(
        zoneResolvers.listZonesWithStatistics.handler({
          items: [
            factory.zoneWithStatistics({
              devices_count: 2,
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<ZonesTable />);

      await waitFor(() => {
        expect(
          within(
            screen.getByRole("row", {
              name: new RegExp(`^default`, "i"),
            })
          ).getByRole("link", { name: "2" })
        ).toHaveAttribute("href", "/devices?zone=default");
      });
    });

    it("can show a controller filter link", async () => {
      mockServer.use(
        zoneResolvers.listZones.handler({
          items: [
            factory.zone({
              name: "default",
            }),
          ],
          total: 1,
        })
      );

      mockServer.use(
        zoneResolvers.listZonesWithStatistics.handler({
          items: [
            factory.zoneWithStatistics({
              controllers_count: 1,
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<ZonesTable />);

      await waitFor(() => {
        expect(
          within(
            screen.getByRole("row", {
              name: new RegExp(`^default`, "i"),
            })
          ).getByRole("link", { name: "1" })
        ).toHaveAttribute("href", "/controllers");
      });
    });
  });

  // TODO: backend-provided permissions is only available for pools,
  //  and will be discussed as to whether they should be added everywhere.
  //  Enable these tests if they are added to zones
  describe("permissions", () => {
    it.todo("enables the action buttons with correct permissions");

    it.todo("disables the action buttons without permissions");

    it("disables the delete button for default zones", async () => {
      mockServer.use(
        zoneResolvers.listZones.handler({
          items: [
            factory.zone({
              id: 1,
              name: "default",
              description: "default",
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<ZonesTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Delete" })
        ).toBeAriaDisabled();
      });
    });
  });

  describe("actions", () => {
    it("opens edit zones side panel form", async () => {
      mockServer.use(
        zoneResolvers.listZones.handler({
          items: [factory.zone({ id: 1 })],
          total: 1,
        })
      );

      renderWithProviders(<ZonesTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Edit" })
        ).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Edit" }));

      expect(mockOpen).toHaveBeenCalledWith({
        component: EditZone,
        title: "Edit AZ",
        props: { id: 1 },
      });
    });

    it("opens delete zone side panel form", async () => {
      mockServer.use(
        zoneResolvers.listZones.handler({
          items: [
            factory.zone({
              id: 2,
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<ZonesTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Delete" })
        ).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Delete" }));

      expect(mockOpen).toHaveBeenCalledWith({
        component: DeleteZone,
        title: "Delete AZ",
        props: { id: 2 },
      });
    });
  });
});
