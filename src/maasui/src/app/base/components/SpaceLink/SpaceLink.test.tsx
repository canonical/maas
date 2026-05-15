import SpaceLink from "./SpaceLink";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

it("handles when spaces are loading", () => {
  const state = factory.rootState({
    space: factory.spaceState({ items: [], loading: true }),
  });

  renderWithProviders(<SpaceLink id={1} />, { state });

  expect(screen.getByLabelText("Loading spaces")).toBeInTheDocument();
});

it("handles when a space does not exist", () => {
  const state = factory.rootState({
    space: factory.spaceState({ items: [], loading: false }),
  });

  renderWithProviders(<SpaceLink id={1} />, { state });

  expect(screen.queryByRole("link")).toBeNull();
  expect(screen.getByText("No space")).toBeInTheDocument();
});

it("renders a link if spaces have loaded and it exists", () => {
  const space = factory.space();
  const state = factory.rootState({
    space: factory.spaceState({ items: [space], loading: false }),
  });

  renderWithProviders(<SpaceLink id={space.id} />, { state });

  expect(screen.getByRole("link")).toHaveAttribute(
    "href",
    urls.networks.space.index({ id: space.id })
  );
});
