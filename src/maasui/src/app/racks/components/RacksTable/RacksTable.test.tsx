import RacksTable from "./RacksTable";

import { rackResolvers } from "@/testing/resolvers/racks";
import {
  mockIsPending,
  renderWithProviders,
  waitFor,
  screen,
  within,
  userEvent,
  setupMockServer,
} from "@/testing/utils";

const mockServer = setupMockServer(rackResolvers.listRacks.handler());

describe("RacksTable", () => {
  describe("display", () => {
    it("displays a loading component if racks are loading", async () => {
      mockIsPending();
      renderWithProviders(<RacksTable />);

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      mockServer.use(rackResolvers.listRacks.handler({ items: [], total: 0 }));
      renderWithProviders(<RacksTable />);

      await waitFor(() => {
        expect(screen.getByText("No racks found.")).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<RacksTable />);

      ["Name", "Registered", "Action"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });

    // TODO : Enable these tests once backend is available https://warthogs.atlassian.net/browse/MAASENG-5529
    it.skip("does not show a controller link for empty racks", async () => {
      // mockServer.use(
      //   rackResolvers.listRacks.handler({
      //     items: [rackFactory.build({ name: "rack_1", registered: [] })],
      //     total: 1,
      //   })
      // );

      renderWithProviders(<RacksTable />);

      await waitFor(() => {
        expect(
          within(
            screen.getByRole("row", {
              name: new RegExp(`^default`, "i"),
            })
          ).getByText("0 controllers")
        ).toBeInTheDocument();
      });
    });

    // TODO : Enable these tests once backend is available https://warthogs.atlassian.net/browse/MAASENG-5529
    it.skip("can show a controller link for non-empty racks", async () => {
      // mockServer.use(
      //   rackResolvers.listRacks.handler({
      //     items: [rackFactory.build({ name: "rack_1", registered: ["controller-1"] })],
      //     total: 1,
      //   })
      // );

      renderWithProviders(<RacksTable />);

      await waitFor(() => {
        expect(
          within(
            screen.getByRole("row", {
              name: new RegExp(`^default`, "i"),
            })
          ).getByRole("link", { name: "1 controller" })
        ).toHaveAttribute("href", "/controllers?system_id=%3Dcontroller-1");
      });
    });
  });

  describe("permissions", () => {
    it.todo("enables the action buttons with correct permissions");

    it.todo("disables the action buttons without permissions");

    // TODO : Enable these tests once backend is available https://warthogs.atlassian.net/browse/MAASENG-5529
    it.skip("disables the delete button for racks that have controllers", async () => {
      // mockServer.use(
      //   rackResolvers.listRacks.handler({
      //     items: [rackFactory.build({ name: "rack_1", registered: ["controller-1"] })],
      //     total: 1,
      //   })
      // );

      renderWithProviders(<RacksTable />);

      await userEvent.click(
        screen.getByRole("button", { name: /take action/i })
      );

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /delete rack/i })
        ).toBeAriaDisabled();
      });
    });

    // TODO : Enable these tests once backend is available https://warthogs.atlassian.net/browse/MAASENG-5529
    it.skip("disables the remove controllers button for racks that have controllers", async () => {
      // mockServer.use(
      //   rackResolvers.listRacks.handler({
      //     items: [rackFactory.build({ name: "rack_1", registered: ["controller-1"] })],
      //     total: 1,
      //   })
      // );

      renderWithProviders(<RacksTable />);

      await userEvent.click(
        screen.getByRole("button", { name: /take action/i })
      );

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /remove controllers/i })
        ).toBeAriaDisabled();
      });
    });
  });

  // TODO : Enable these tests once backend is available https://warthogs.atlassian.net/browse/MAASENG-5529
  it.skip("disables the register controller button for racks that have three controllers", async () => {
    // mockServer.use(
    //   rackResolvers.listRacks.handler({
    //     items: [rackFactory.build({ name: "rack_1", registered: ["controller-1", "controller-2", "controller-3"] })],
    //     total: 1,
    //   })
    // );

    renderWithProviders(<RacksTable />);

    await userEvent.click(screen.getByRole("button", { name: /take action/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /register controller/i })
      ).toBeAriaDisabled();
    });
  });

  describe("actions", () => {
    it.todo("opens edit rack side panel form");

    it.todo("opens delete rack side panel form");

    it.todo("opens register controller side panel form");

    it.todo("opens remove controllers side panel form");
  });
});
