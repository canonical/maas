import NetworkDiscoveryHeader, {
  Labels as NetworkDiscoveryHeaderLabels,
} from "./NetworkDiscoveryHeader";

import { ClearAllForm } from "@/app/networkDiscovery/components";
import { networkDiscoveryResolvers } from "@/testing/resolvers/networkDiscovery";
import {
  screen,
  renderWithProviders,
  userEvent,
  setupMockServer,
  mockSidePanel,
} from "@/testing/utils";

setupMockServer(networkDiscoveryResolvers.listNetworkDiscoveries.handler());
const { mockOpen } = await mockSidePanel();

describe("NetworkDiscoveryHeader", () => {
  it("has a button to clear discoveries", () => {
    renderWithProviders(<NetworkDiscoveryHeader />);
    expect(
      screen.getByRole("button", {
        name: NetworkDiscoveryHeaderLabels.ClearAll,
      })
    ).toBeInTheDocument();
  });

  it("opens the side panel when the 'Clear all discoveries' button is clicked", async () => {
    renderWithProviders(<NetworkDiscoveryHeader />);

    await userEvent.click(
      screen.getByRole("button", {
        name: NetworkDiscoveryHeaderLabels.ClearAll,
      })
    );
    expect(mockOpen).toHaveBeenCalledWith({
      component: ClearAllForm,
      title: "Clear all discoveries",
    });
  });
});
