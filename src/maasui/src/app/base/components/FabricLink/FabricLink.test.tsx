import FabricLink, { Labels } from "./FabricLink";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

it("handles when fabrics are loading", () => {
  const state = factory.rootState({
    fabric: factory.fabricState({ items: [], loading: true }),
  });

  renderWithProviders(<FabricLink id={1} />, { state });

  expect(screen.getByLabelText(Labels.Loading)).toBeInTheDocument();
});

it("handles when a fabric does not exist", () => {
  const state = factory.rootState({
    fabric: factory.fabricState({ items: [], loading: false }),
  });

  renderWithProviders(<FabricLink id={1} />, { state });

  expect(screen.queryByText(/.+/)).not.toBeInTheDocument();
});

it("renders a link if fabrics have loaded and it exists", () => {
  const fabric = factory.fabric();
  const state = factory.rootState({
    fabric: factory.fabricState({ items: [fabric], loading: false }),
  });

  renderWithProviders(<FabricLink id={fabric.id} />, { state });

  expect(screen.getByRole("link")).toHaveAttribute(
    "href",
    urls.networks.fabric.index({ id: fabric.id })
  );
});
