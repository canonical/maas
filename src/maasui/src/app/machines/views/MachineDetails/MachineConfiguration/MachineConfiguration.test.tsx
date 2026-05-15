import { screen } from "@testing-library/react";

import MachineConfiguration from "./MachineConfiguration";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

describe("MachineConfiguration", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machine({ system_id: "abc123" })],
      }),
    });
  });

  it("displays a spinner if machine has not loaded yet", () => {
    state.machine.items = [];

    renderWithProviders(<MachineConfiguration />, {
      state,
      initialEntries: ["/machine/abc123"],
    });
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });
});
