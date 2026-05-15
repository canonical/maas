import SubnetSpace from "./SubnetSpace";

import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

it("shows a warning tooltip if the subnet is not in a space", async () => {
  const state = factory.rootState();
  renderWithProviders(<SubnetSpace spaceId={null} />, { state });

  await userEvent.click(screen.getByRole("button"));

  expect(
    screen.getByRole("tooltip", {
      name: /This subnet does not belong to a space/,
    })
  ).toBeInTheDocument();
});

it("does not show a warning tooltip if the subnet is in a space", async () => {
  const state = factory.rootState();
  renderWithProviders(<SubnetSpace spaceId={1} />, { state });

  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
