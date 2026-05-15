import { waitFor } from "@testing-library/react";

import EditRack from "./EditRack";

import { rackResolvers } from "@/testing/resolvers/racks";
import {
  userEvent,
  screen,
  setupMockServer,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  rackResolvers.getRack.handler(),
  rackResolvers.updateRack.handler()
);
const { mockClose } = await mockSidePanel();

describe("EditRack", () => {
  const testRackId = 1;

  it("runs closeForm function when the cancel button is clicked", async () => {
    renderWithProviders(<EditRack id={testRackId} />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Cancel" })
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls update rack on save click", async () => {
    renderWithProviders(<EditRack id={testRackId} />);

    await waitFor(() => {
      expect(screen.getByLabelText("* Name")).toBeInTheDocument();
    });

    await userEvent.clear(screen.getByLabelText("* Name"));

    await userEvent.type(
      screen.getByRole("textbox", { name: /name/i }),
      "test name 2"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save rack/i }));

    await waitFor(() => {
      expect(rackResolvers.updateRack.resolved).toBeTruthy();
    });
  });

  it("displays error message when update rack fails", async () => {
    mockServer.use(
      rackResolvers.updateRack.error({ code: 400, message: "Uh oh!" }),
      rackResolvers.updateRack.handler()
    );

    renderWithProviders(<EditRack id={testRackId} />);

    await waitFor(() => {
      expect(screen.getByLabelText("* Name")).toBeInTheDocument();
    });

    await userEvent.type(
      screen.getByRole("textbox", { name: /name/i }),
      "test"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save rack/i }));

    await waitFor(() => {
      expect(screen.getByText("Uh oh!")).toBeInTheDocument();
    });
  });
});
