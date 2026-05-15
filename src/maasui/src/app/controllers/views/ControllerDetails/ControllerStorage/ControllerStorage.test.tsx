import ControllerStorage from "./ControllerStorage";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

it("displays a spinner if controller is loading", () => {
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [],
    }),
  });
  renderWithProviders(<ControllerStorage systemId="abc123" />, { state });

  expect(
    screen.getByRole("alert", { name: "Loading controller" })
  ).toBeInTheDocument();
});
