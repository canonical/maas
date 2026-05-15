import { CoresColumn } from "./CoresColumn";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

describe("CoresColumn", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machine({
            system_id: "abc123",
            architecture: "amd64/generic",
            cpu_count: 4,
            cpu_test_status: factory.testStatus({
              status: 1,
            }),
          }),
        ],
      }),
    });
  });

  it("displays the number of cores", () => {
    state.machine.items[0].cpu_count = 8;

    renderWithProviders(<CoresColumn systemId="abc123" />, {
      state,
    });
    expect(screen.getByLabelText("Cores")).toHaveTextContent("8");
  });

  it("truncates architecture", () => {
    state.machine.items[0].architecture = "i386/generic";

    renderWithProviders(<CoresColumn systemId="abc123" />, {
      state,
    });
    expect(screen.getByTestId("arch")).toHaveTextContent("i386");
  });

  it("displays a Tooltip with the full architecture", async () => {
    state.machine.items[0].architecture = "amd64/generic";

    renderWithProviders(<CoresColumn systemId="abc123" />, {
      state,
    });

    await userEvent.hover(screen.getByTestId("arch"));
    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent("amd64/generic");
    });
  });
});
