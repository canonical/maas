import DeleteRack from "./DeleteRack";

import { rackResolvers } from "@/testing/resolvers/racks";
import {
  mockSidePanel,
  renderWithProviders,
  setupMockServer,
  userEvent,
  screen,
  waitFor,
  waitForLoading,
} from "@/testing/utils";

const mockServer = setupMockServer(
  rackResolvers.getRack.handler(),
  rackResolvers.deleteRack.handler()
);
const { mockClose } = await mockSidePanel();

describe("DeleteRack", () => {
  it("calls closeForm on cancel click", async () => {
    renderWithProviders(<DeleteRack id={2} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls delete rack on save click", async () => {
    renderWithProviders(<DeleteRack id={2} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: /Delete/i }));
    await waitFor(() => {
      expect(rackResolvers.deleteRack.resolved).toBeTruthy();
    });
  });

  it("displays error messages when delete rack fails", async () => {
    mockServer.use(
      rackResolvers.deleteRack.error({ code: 400, message: "Uh oh!" })
    );
    renderWithProviders(<DeleteRack id={2} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
