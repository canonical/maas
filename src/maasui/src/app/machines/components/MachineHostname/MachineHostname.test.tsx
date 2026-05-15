import MachineHostname from "./MachineHostname";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

it("displays machine systemId when hostname is not available", async () => {
  renderWithProviders(<MachineHostname systemId="abc123" />);
  expect(screen.getByText(/abc123/i)).toBeInTheDocument();
});

it("displays machine hostname once loaded", () => {
  const state = factory.rootState();
  state.machine.items = [
    factory.machine({
      system_id: "abc123",
      hostname: "test-machine",
    }),
  ];
  state.machine.details = {
    "mocked-nanoid": factory.machineStateDetailsItem({
      system_id: "abc123",
    }),
  };
  renderWithProviders(<MachineHostname systemId="abc123" />, { state });
  expect(screen.getByText(/test-machine/i)).toBeInTheDocument();
});
