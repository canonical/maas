import { waitFor } from "@testing-library/react";

import AddRack from "./AddRack";

import { rackResolvers } from "@/testing/resolvers/racks";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
} from "@/testing/utils";

const mockServer = setupMockServer(rackResolvers.createRack.handler());
const { mockClose } = await mockSidePanel();

describe("AddRack", () => {
  it("runs closeForm function when the cancel button is clicked", async () => {
    renderWithProviders(<AddRack />);

    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls create rack on save click", async () => {
    renderWithProviders(<AddRack />);

    await userEvent.type(
      screen.getByRole("textbox", { name: /name/i }),
      "test-rack"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save rack/i }));

    await waitFor(() => {
      expect(rackResolvers.createRack.resolved).toBeTruthy();
    });
  });

  it("displays error message when create rack fails", async () => {
    mockServer.use(
      rackResolvers.createRack.error({ code: 400, message: "Uh oh!" })
    );

    renderWithProviders(<AddRack />);

    await userEvent.type(
      screen.getByRole("textbox", { name: /name/i }),
      "danger-zone"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save rack/i }));

    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
