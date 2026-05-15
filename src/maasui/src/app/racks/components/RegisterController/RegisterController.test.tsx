import RegisterController from "./RegisterController";

import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

describe("RegisterController", () => {
  const testRackId = 1;

  it("renders GuidedProvisioning as default", () => {
    renderWithProviders(<RegisterController id={testRackId} />);
    expect(
      screen.getByRole("button", { name: /Generate token/i })
    ).toBeInTheDocument();
  });
  it("renders OneTouchProvisioning when selected", async () => {
    renderWithProviders(<RegisterController id={testRackId} />);
    await userEvent.click(screen.getByLabelText("One-touch provisioning"));
    await waitFor(() => {
      expect(screen.getByLabelText(/MAAS Agent secret/i)).toBeInTheDocument();
    });
  });
});
