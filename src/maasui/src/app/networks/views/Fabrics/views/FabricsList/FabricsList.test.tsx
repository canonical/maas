import FabricsList from "./FabricsList";

import { fabricsResolvers, mockFabrics } from "@/testing/resolvers/fabrics";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

setupMockServer(fabricsResolvers.listFabrics.handler());

describe("FabricsList", () => {
  it("uses the correct window title", async () => {
    renderWithProviders(<FabricsList />);

    expect(document.title).toBe("Fabrics | MAAS");
  });

  it("renders the Fabrics table", () => {
    renderWithProviders(<FabricsList />);

    expect(
      screen.getByRole("grid", { name: "Fabrics table" })
    ).toBeInTheDocument();
  });

  it("renders the DeleteFabric form", async () => {
    renderWithProviders(<FabricsList />);

    await waitFor(() => {
      expect(
        screen.getByText(`${mockFabrics.items[0].name}`)
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);

    expect(
      screen.getByRole("complementary", { name: "Delete fabric" })
    ).toBeInTheDocument();
  });
});
