import { RamColumn } from "./RamColumn";

import type { RootState } from "@/app/store/root/types";
import { TestStatusStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("RamColumn", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        errors: {},
        loading: false,
        loaded: true,
        items: [
          factory.machine({
            system_id: "abc123",
            memory: 8,
            memory_test_status: factory.testStatus({
              status: 2,
            }),
          }),
        ],
      }),
    });
  });

  it("displays ram amount", () => {
    state.machine.items[0].memory = 16;

    renderWithProviders(<RamColumn systemId="abc123" />, {
      state,
    });

    expect(screen.getByTestId("memory")).toHaveTextContent("16");
  });

  it("displays an error and tooltip if memory tests have failed", async () => {
    state.machine.items[0].memory = 16;
    state.machine.items[0].memory_test_status = factory.testStatus({
      status: TestStatusStatus.FAILED,
    });

    renderWithProviders(<RamColumn systemId="abc123" />, {
      state,
    });

    await userEvent.click(screen.getByRole("button", { name: /error/i }));
    expect(screen.getByRole("tooltip")).toHaveTextContent(
      "Machine has failed tests."
    );
    expect(screen.getByLabelText("error")).toHaveClass("p-icon--error");
  });
});
