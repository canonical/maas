import MachineNetwork from "./MachineNetwork";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

const machineRoutePattern = `${urls.machines.machine.index(null)}/*`;
const networkUrl = urls.machines.machine.network({ id: "abc123" });

it("displays a spinner if machine is loading", () => {
  const state = factory.rootState({
    machine: factory.machineState({
      items: [],
    }),
  });
  renderWithProviders(<MachineNetwork />, {
    state,
    initialEntries: [networkUrl],
    pattern: machineRoutePattern,
  });
  expect(screen.getByLabelText("Loading machine")).toBeInTheDocument();
  expect(screen.queryByLabelText("Machine network")).not.toBeInTheDocument();
});

it("displays the network tab when loaded", () => {
  const state = factory.rootState({
    machine: factory.machineState({
      items: [factory.machineDetails({ system_id: "abc123" })],
    }),
  });
  renderWithProviders(<MachineNetwork />, {
    state,
    initialEntries: [networkUrl],
    pattern: machineRoutePattern,
  });
  expect(screen.queryByLabelText("Loading machine")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Machine network")).toBeInTheDocument();
});
