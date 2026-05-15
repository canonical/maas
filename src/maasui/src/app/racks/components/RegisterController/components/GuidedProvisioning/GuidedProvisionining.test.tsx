import GuidedProvisioning from "./GuidedProvisioning";

import { rackResolvers } from "@/testing/resolvers/racks";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

setupMockServer(rackResolvers.generateToken.handler());
const { mockClose } = await mockSidePanel();

describe("GuidedProvisioning", () => {
  const testRackId = 1;

  it("provides correct instructions for first command snippet", () => {
    renderWithProviders(<GuidedProvisioning id={testRackId} />);
    const instructions = screen.getByTestId("first-command-snippet");
    expect(
      within(instructions).getByText(
        new RegExp("sudo snap install maas-agent --channel=3.7")
      )
    ).toBeInTheDocument();
  });

  it("provides correct instructions for second command snippet", () => {
    renderWithProviders(<GuidedProvisioning id={testRackId} />);
    const instructions = screen.getByTestId("second-command-snippet");
    expect(
      within(instructions).getByText(
        new RegExp("maas-agent init --token <TOKEN>")
      )
    ).toBeInTheDocument();
  });

  it("calls generate token on generate token click", async () => {
    renderWithProviders(<GuidedProvisioning id={testRackId} />);

    await userEvent.click(
      screen.getByRole("button", { name: /Generate token/i })
    );

    await waitFor(() => {
      expect(rackResolvers.generateToken.resolved).toBeTruthy();
    });
  });

  it("can close the instructions", async () => {
    renderWithProviders(<GuidedProvisioning id={testRackId} />);

    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(mockClose).toHaveBeenCalled();
  });
});
