import ControllerLink, { Labels } from "./ControllerLink";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

it("handles when controllers are loading", () => {
  const state = factory.rootState({
    controller: factory.controllerState({ items: [], loading: true }),
  });

  renderWithProviders(<ControllerLink systemId="abc123" />, { state });

  expect(screen.getByLabelText(Labels.LoadingControllers)).toBeInTheDocument();
});

it("handles when a controller does not exist", () => {
  const state = factory.rootState({
    controller: factory.controllerState({ items: [], loading: false }),
  });

  renderWithProviders(<ControllerLink systemId="abc123" />, { state });

  expect(screen.queryByText(/.+/)).not.toBeInTheDocument();
});

it("renders a link if controllers have loaded and it exists", () => {
  const controller = factory.controller({
    domain: factory.modelRef({ name: "maas" }),
    hostname: "bolla",
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
      loading: false,
    }),
  });

  renderWithProviders(<ControllerLink systemId={controller.system_id} />, {
    state,
  });

  const link = screen.getByRole("link");
  expect(link).toHaveTextContent("bolla.maas");
  expect(link).toHaveAttribute(
    "href",
    urls.controllers.controller.index({ id: controller.system_id })
  );
});
