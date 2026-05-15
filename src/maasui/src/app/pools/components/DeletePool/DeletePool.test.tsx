import DeletePool from "./DeletePool";

import { poolsResolvers } from "@/testing/resolvers/pools";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
  waitForLoading,
} from "@/testing/utils";

const mockServer = setupMockServer(
  poolsResolvers.getPool.handler(),
  poolsResolvers.deletePool.handler()
);
const { mockClose } = await mockSidePanel();

describe("DeletePool", () => {
  it("calls closeForm on cancel click", async () => {
    renderWithProviders(<DeletePool id={2} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls delete pool on save click", async () => {
    renderWithProviders(<DeletePool id={2} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: /Delete/i }));
    await waitFor(() => {
      expect(poolsResolvers.deletePool.resolved).toBeTruthy();
    });
  });

  it("displays error messages when delete pool fails", async () => {
    mockServer.use(
      poolsResolvers.deletePool.error({ code: 400, message: "Uh oh!" })
    );
    renderWithProviders(<DeletePool id={2} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
