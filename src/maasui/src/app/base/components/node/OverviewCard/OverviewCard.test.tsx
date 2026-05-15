import OverviewCard from "./OverviewCard";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

it("renders a controller status section if node is a controller", () => {
  const controller = factory.controllerDetails();
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
  });
  renderWithProviders(<OverviewCard node={controller} />, { state });

  expect(screen.getByTestId("controller-status")).toBeInTheDocument();
  expect(screen.queryByTestId("machine-status")).not.toBeInTheDocument();
});

it("renders a machine status section if node is a machine", () => {
  const machine = factory.machineDetails();
  const state = factory.rootState({
    machine: factory.machineState({
      items: [machine],
    }),
  });
  renderWithProviders(<OverviewCard node={machine} />, { state });

  expect(screen.getByTestId("machine-status")).toBeInTheDocument();
  expect(screen.queryByTestId("controller-status")).not.toBeInTheDocument();
});
