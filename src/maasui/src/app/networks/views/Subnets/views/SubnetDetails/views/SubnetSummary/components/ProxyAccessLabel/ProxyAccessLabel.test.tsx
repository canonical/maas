import ProxyAccessLabel from "./ProxyAccessLabel";

import { userEvent, screen, renderWithProviders } from "@/testing/utils";

it("shows a tooltip when proxy access is allowed", async () => {
  renderWithProviders(<ProxyAccessLabel allowProxy />);

  await userEvent.click(screen.getByRole("button"));

  expect(
    screen.getByRole("tooltip", { name: /MAAS will allow clients/ })
  ).toBeInTheDocument();
});

it("shows a tooltip when proxy access is not allowed", async () => {
  renderWithProviders(<ProxyAccessLabel allowProxy={false} />);

  await userEvent.click(screen.getByRole("button"));

  expect(
    screen.getByRole("tooltip", { name: /MAAS will not allow clients/ })
  ).toBeInTheDocument();
});
