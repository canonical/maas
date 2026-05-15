import FabricsTable from "./FabricsTable";

import { DeleteFabric } from "@/app/networks/views/Fabrics/components";
import { fabricsResolvers, mockFabrics } from "@/testing/resolvers/fabrics";
import {
  mockIsPending,
  mockSidePanel,
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();
const mockServer = setupMockServer(fabricsResolvers.listFabrics.handler());

describe("FabricsTable", () => {
  describe("display", () => {
    it("displays a spinner while loading", () => {
      mockIsPending();

      renderWithProviders(<FabricsTable />);

      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    it("displays an error message if an error is encountered while fetching", async () => {
      mockServer.use(
        fabricsResolvers.listFabrics.error({
          message: "Uh oh!",
          code: 400,
          kind: "Error",
        })
      );
      renderWithProviders(<FabricsTable />);

      await waitFor(() => {
        expect(
          screen.getByText("Error while fetching fabrics")
        ).toBeInTheDocument();
      });

      expect(screen.getByText("Uh oh!")).toBeInTheDocument();
    });

    it("displays an appropriate message when there are no Fabrics", async () => {
      mockServer.use(
        fabricsResolvers.listFabrics.handler({ items: [], total: 0 })
      );
      renderWithProviders(<FabricsTable />);

      await waitFor(() => {
        expect(screen.getByText("No fabrics found.")).toBeInTheDocument();
      });
    });
  });

  describe("actions", () => {
    it("opens the Delete Fabric form when the Delete button is clicked", async () => {
      renderWithProviders(<FabricsTable />);

      await waitFor(() => {
        expect(
          screen.getByText(`${mockFabrics.items[0].name}`)
        ).toBeInTheDocument();
      });

      await userEvent.click(
        screen.getAllByRole("button", { name: "Delete" })[0]
      );

      await waitFor(() => {
        expect(mockOpen).toHaveBeenCalledWith({
          component: DeleteFabric,
          title: "Delete fabric",
          props: {
            id: mockFabrics.items[0].id,
          },
        });
      });
    });
  });
});
