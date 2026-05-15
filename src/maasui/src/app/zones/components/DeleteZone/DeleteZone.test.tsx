import DeleteZone from "./DeleteZone";

import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  userEvent,
  screen,
  setupMockServer,
  waitFor,
  renderWithProviders,
  mockSidePanel,
  waitForLoading,
} from "@/testing/utils";

const mockServer = setupMockServer(
  zoneResolvers.getZone.handler(),
  zoneResolvers.deleteZone.handler()
);
const { mockClose } = await mockSidePanel();

describe("DeleteZone", () => {
  it("calls closeSidePanel on cancel click", async () => {
    renderWithProviders(<DeleteZone id={2} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls delete zone on save click", async () => {
    renderWithProviders(<DeleteZone id={2} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: /Delete/i }));
    await waitFor(() => {
      expect(zoneResolvers.deleteZone.resolved).toBeTruthy();
    });
  });

  it("displays error messages when delete zone fails", async () => {
    mockServer.use(
      zoneResolvers.deleteZone.error({ code: 400, message: "Uh oh!" })
    );
    renderWithProviders(<DeleteZone id={2} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
