import ActiveDiscoveryLabel from "./ActiveDiscoveryLabel";

import { userEvent, screen, renderWithProviders } from "@/testing/utils";

it("displays a tooltip", async () => {
  renderWithProviders(<ActiveDiscoveryLabel />);

  await userEvent.click(screen.getByRole("button"));

  expect(
    screen.getByRole("tooltip", {
      name: /When enabled, MAAS will scan this subnet/,
    })
  ).toBeInTheDocument();
});
