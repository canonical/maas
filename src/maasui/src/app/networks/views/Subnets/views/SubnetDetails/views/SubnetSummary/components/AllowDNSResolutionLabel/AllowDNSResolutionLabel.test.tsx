import AllowDNSResolutionLabel from "./AllowDNSResolutionLabel";

import { userEvent, screen, renderWithProviders } from "@/testing/utils";

it("shows a tooltip when DNS is allowed", async () => {
  renderWithProviders(<AllowDNSResolutionLabel allowDNS />);

  await userEvent.click(screen.getByRole("button"));

  expect(
    screen.getByRole("tooltip", { name: /MAAS will allow clients/ })
  ).toBeInTheDocument();
});

it("shows a tooltip when DNS is not allowed", async () => {
  renderWithProviders(<AllowDNSResolutionLabel allowDNS={false} />);

  await userEvent.click(screen.getByRole("button"));

  expect(
    screen.getByRole("tooltip", { name: /MAAS will not allow clients/ })
  ).toBeInTheDocument();
});
