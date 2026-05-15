import SpacesTable from "./SpacesTable";

import { DeleteSpace } from "@/app/networks/views/Spaces/components";
import { mockSpaces, spacesResolvers } from "@/testing/resolvers/spaces";
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
const mockServer = setupMockServer(spacesResolvers.listSpaces.handler());

describe("SpacesTable", () => {
  describe("display", () => {
    it("displays a spinner while loading", () => {
      mockIsPending();

      renderWithProviders(<SpacesTable />);

      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    it("displays an error message if an error is encountered while fetching", async () => {
      mockServer.use(
        spacesResolvers.listSpaces.error({
          message: "Uh oh!",
          code: 400,
          kind: "Error",
        })
      );
      renderWithProviders(<SpacesTable />);

      await waitFor(() => {
        expect(
          screen.getByText("Error while fetching spaces")
        ).toBeInTheDocument();
      });

      expect(screen.getByText("Uh oh!")).toBeInTheDocument();
    });

    it("displays an appropriate message when there are no Spaces", async () => {
      mockServer.use(
        spacesResolvers.listSpaces.handler({ items: [], total: 0 })
      );
      renderWithProviders(<SpacesTable />);

      await waitFor(() => {
        expect(screen.getByText("No spaces found.")).toBeInTheDocument();
      });
    });
  });

  describe("actions", () => {
    it("opens the Delete Space form when the Delete button is clicked", async () => {
      renderWithProviders(<SpacesTable />);

      await waitFor(() => {
        expect(
          screen.getByText(`${mockSpaces.items[0].name}`)
        ).toBeInTheDocument();
      });

      await userEvent.click(
        screen.getAllByRole("button", { name: "Delete" })[0]
      );

      await waitFor(() => {
        expect(mockOpen).toHaveBeenCalledWith({
          component: DeleteSpace,
          title: "Delete space",
          props: {
            id: mockSpaces.items[0].id,
          },
        });
      });
    });
  });
});
