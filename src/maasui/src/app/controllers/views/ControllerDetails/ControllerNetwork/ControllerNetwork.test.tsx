import ControllerNetwork from "./ControllerNetwork";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

it("displays a spinner if controller is loading", () => {
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [],
    }),
  });
  renderWithProviders(<ControllerNetwork systemId="abc123" />, {
    state,
  });
  expect(screen.getByLabelText("Loading controller")).toBeInTheDocument();
  expect(screen.queryByLabelText("Controller network")).not.toBeInTheDocument();
});

it("displays the network tab when loaded", () => {
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [factory.controllerDetails({ system_id: "abc123" })],
    }),
  });
  renderWithProviders(<ControllerNetwork systemId="abc123" />, {
    state,
  });
  expect(screen.queryByLabelText("Loading controller")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Controller network")).toBeInTheDocument();
});
