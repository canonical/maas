import { DisksColumn } from "./DisksColumn";

import type { RootState } from "@/app/store/root/types";
import { TestStatusStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

describe("DisksColumn", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machine({
            system_id: "abc123",
            physical_disk_count: 1,
            storage_test_status: factory.testStatus({
              status: 2,
            }),
          }),
        ],
      }),
    });
  });

  it("displays the physical disk count", () => {
    state.machine.items[0].physical_disk_count = 2;

    renderWithProviders(<DisksColumn systemId="abc123" />, {
      state,
    });
    expect(screen.getByTestId("primary")).toHaveTextContent("2");
  });

  it("correctly shows error icon and tooltip if storage tests failed", async () => {
    state.machine.items[0].storage_test_status = factory.testStatus({
      status: TestStatusStatus.FAILED,
    });

    renderWithProviders(<DisksColumn systemId="abc123" />, {
      state,
    });

    expect(screen.getByLabelText("error")).toHaveClass("p-icon--error");

    await userEvent.hover(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent(
        "Machine has failed tests."
      );
    });
  });
});
