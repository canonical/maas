import SpacesList from "./SpacesList";

import { mockSpaces, spacesResolvers } from "@/testing/resolvers/spaces";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

setupMockServer(spacesResolvers.listSpaces.handler());

describe("SpacesList", () => {
  it("uses the correct window title", async () => {
    renderWithProviders(<SpacesList />);

    expect(document.title).toBe("Spaces | MAAS");
  });

  it("renders the Spaces table", () => {
    renderWithProviders(<SpacesList />);

    expect(
      screen.getByRole("grid", { name: "Spaces table" })
    ).toBeInTheDocument();
  });

  it("renders the DeleteSpace form", async () => {
    renderWithProviders(<SpacesList />);

    await waitFor(() => {
      expect(
        screen.getByText(`${mockSpaces.items[0].name}`)
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);

    expect(
      screen.getByRole("complementary", { name: "Delete space" })
    ).toBeInTheDocument();
  });
});
