import SubnetLink from "./SubnetLink";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

it("handles when subnets are loading", () => {
  const state = factory.rootState({
    subnet: factory.subnetState({ items: [], loading: true }),
  });

  renderWithProviders(<SubnetLink id={1} />, { state });

  expect(screen.getByLabelText("Loading subnets")).toBeInTheDocument();
});

it("handles when a subnet does not exist", () => {
  const state = factory.rootState({
    subnet: factory.subnetState({ items: [], loading: false }),
  });

  renderWithProviders(<SubnetLink id={1} />, { state });

  expect(screen.queryByRole("link")).toBeNull();
  expect(screen.getByText("Unconfigured")).toBeInTheDocument();
});

it("renders a link if subnets have loaded and it exists", () => {
  const subnet = factory.subnet();
  const state = factory.rootState({
    subnet: factory.subnetState({ items: [subnet], loading: false }),
  });

  renderWithProviders(<SubnetLink id={subnet.id} />, { state });

  expect(screen.getByRole("link")).toHaveAttribute(
    "href",
    urls.networks.subnet.index({ id: subnet.id })
  );
});
