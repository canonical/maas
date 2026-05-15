import FabricControllers from "./FabricControllers";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

it("displays a spinner when loading controllers", () => {
  const controller = factory.controller({
    hostname: "controller-1",
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      loaded: true,
      items: [controller],
    }),
  });
  const fabric = factory.fabric({ id: 1 });

  renderWithProviders(<FabricControllers id={fabric.id} />, { state });

  expect(screen.getByTestId("Spinner")).toBeInTheDocument();
});
