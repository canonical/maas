import ManagedAllocationLabel from "./ManagedAllocationLabel";

import { userEvent, screen, renderWithProviders } from "@/testing/utils";

it("shows a tooltip", async () => {
  renderWithProviders(<ManagedAllocationLabel />);

  await userEvent.click(screen.getByRole("button"));

  expect(
    screen.getByRole("tooltip", {
      name: /MAAS allocates IP addresses from this subnet/,
    })
  ).toBeInTheDocument();
});
