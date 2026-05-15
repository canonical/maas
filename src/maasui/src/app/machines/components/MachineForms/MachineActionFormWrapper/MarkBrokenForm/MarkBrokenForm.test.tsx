import MarkBrokenForm from "./MarkBrokenForm";

import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("MarkBrokenForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machine({ system_id: "abc123" }),
          factory.machine({ system_id: "def456" }),
        ],
        statuses: {
          abc123: factory.machineStatus({ markingBroken: false }),
          def456: factory.machineStatus({ markingBroken: false }),
        },
        selected: { items: ["abc123", "def456"] },
      }),
    });
  });

  it("dispatches actions to mark given machines broken", async () => {
    const { store } = renderWithProviders(
      <MarkBrokenForm isViewingDetails={false} />,
      { state }
    );

    const commentInput = screen.getByLabelText(
      "Add error description to 2 machines"
    );
    await userEvent.type(commentInput, "machine is on fire");

    const submitButton = screen.getByRole("button", {
      name: "Mark 2 machines broken",
    });
    await userEvent.click(submitButton);

    expect(
      store
        .getActions()
        .filter((action) => action.type === "machine/markBroken")
    ).toMatchObject([
      {
        type: "machine/markBroken",
        meta: {
          model: "machine",
          method: "action",
        },
        payload: {
          params: {
            action: NodeActions.MARK_BROKEN,
            extra: {
              message: "machine is on fire",
            },
            system_id: undefined,
            filter: {
              id: ["abc123", "def456"],
            },
          },
        },
      },
    ]);
  });

  it("dispatches actions to mark selected machines broken without a message", async () => {
    state.machine.selected = { items: ["abc123"] };
    const { store } = renderWithProviders(
      <MarkBrokenForm isViewingDetails={false} />,
      { state }
    );

    const submitButton = screen.getByRole("button", {
      name: "Mark machine broken",
    });
    await userEvent.click(submitButton);

    expect(
      store.getActions().find((action) => action.type === "machine/markBroken")
    ).toMatchObject({
      type: "machine/markBroken",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.MARK_BROKEN,
          extra: {
            message: "",
          },
          system_id: undefined,
          filter: {
            id: ["abc123"],
          },
        },
      },
    });
  });
});
