import VLANLink from "./VLANLink";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

it("handles when VLANs are loading", () => {
  const state = factory.rootState({
    vlan: factory.vlanState({ items: [], loading: true }),
  });

  renderWithProviders(<VLANLink id={1} />, { state });

  expect(screen.getByLabelText("Loading VLANs")).toBeInTheDocument();
});

it("handles when a VLAN does not exist", () => {
  const state = factory.rootState({
    vlan: factory.vlanState({ items: [], loading: false }),
  });

  renderWithProviders(<VLANLink id={1} />, { state });

  expect(screen.queryByText(/.+/)).not.toBeInTheDocument();
});

it("renders a link if VLANs have loaded and it exists", () => {
  const vlan = factory.vlan();
  const state = factory.rootState({
    vlan: factory.vlanState({ items: [vlan], loading: false }),
  });

  renderWithProviders(<VLANLink id={vlan.id} />, { state });

  expect(screen.getByRole("link")).toHaveAttribute(
    "href",
    urls.networks.vlan.index({ id: vlan.id })
  );
});
