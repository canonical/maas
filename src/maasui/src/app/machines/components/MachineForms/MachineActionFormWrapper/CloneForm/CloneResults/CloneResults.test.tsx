import CloneResults, { CloneErrorCodes } from "./CloneResults";

import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { screen, userEvent, renderWithProviders } from "@/testing/utils";

describe("CloneResults", () => {
  let state: RootState;
  let machine: MachineDetails;

  beforeEach(() => {
    machine = factory.machineDetails({ system_id: "abc123" });
    state = factory.rootState({
      machine: factory.machineState({ items: [machine], loaded: true }),
    });
  });

  it("handles a successful clone result", () => {
    state.machine.eventErrors = [];

    renderWithProviders(
      <CloneResults
        closeForm={vi.fn()}
        selectedCount={2}
        sourceMachine={machine}
      />,
      {
        initialEntries: [{ pathname: "/machines", key: "testKey" }],
        state,
      }
    );
    expect(
      screen.getByText(/2 of 2 machines cloned successfully from/i)
    ).toBeInTheDocument();
    expect(screen.queryByTestId("error-filter-link")).not.toBeInTheDocument();
  });

  it("handles global clone errors", () => {
    state.machine.eventErrors = [
      factory.machineEventError({
        error: "it didn't work",
        event: NodeActions.CLONE,
        id: machine.system_id,
      }),
    ];

    renderWithProviders(
      <CloneResults
        closeForm={vi.fn()}
        selectedCount={2}
        sourceMachine={machine}
      />,
      {
        initialEntries: [{ pathname: "/machines", key: "testKey" }],
        state,
      }
    );
    expect(
      screen.getByText(/0 of 2 machines cloned successfully from/i)
    ).toBeInTheDocument();
    expect(screen.getByTestId("error-description")).toHaveTextContent(
      "Cloning was unsuccessful: it didn't work"
    );
  });

  it("handles non-invalid item destination errors", () => {
    state.machine.eventErrors = [
      factory.machineEventError({
        error: {
          destinations: [
            {
              code: CloneErrorCodes.STORAGE,
              message: "Invalid storage",
              system_id: "def456",
            },
          ],
        },
        event: NodeActions.CLONE,
        id: machine.system_id,
      }),
    ];

    renderWithProviders(
      <CloneResults
        closeForm={vi.fn()}
        selectedCount={2}
        sourceMachine={machine}
      />,
      {
        initialEntries: [{ pathname: "/machines", key: "testKey" }],
        state,
      }
    );
    expect(
      screen.getByText(/1 of 2 machines cloned successfully from/i)
    ).toBeInTheDocument();
    expect(screen.getByTestId("error-filter-link")).toHaveAttribute(
      "href",
      "/machines?system_id=def456"
    );
  });

  it("handles invalid item destination errors", () => {
    state.machine.eventErrors = [
      factory.machineEventError({
        error: {
          destinations: [
            {
              code: CloneErrorCodes.ITEM_INVALID,
              message:
                "Machine 1 is invalid: Select a valid choice. def456 is not one of the available choices.",
            },
          ],
        },
        event: NodeActions.CLONE,
        id: machine.system_id,
      }),
    ];

    renderWithProviders(
      <CloneResults
        closeForm={vi.fn()}
        selectedCount={2}
        sourceMachine={machine}
      />,
      {
        initialEntries: [{ pathname: "/machines", key: "testKey" }],
        state,
      }
    );
    expect(
      screen.getByText(/0 of 2 machines cloned successfully from/i)
    ).toBeInTheDocument();
    expect(screen.getByTestId("error-filter-link")).toHaveAttribute(
      "href",
      "/machines?system_id=def456"
    );
  });

  it("groups errors by error code", () => {
    state.machine.eventErrors = [
      factory.machineEventError({
        error: {
          destinations: [
            {
              code: CloneErrorCodes.STORAGE,
              message: "Invalid storage",
              system_id: "def456",
            },
            {
              code: CloneErrorCodes.STORAGE,
              message: "Invalid storage",
              system_id: "ghi789",
            },
            {
              code: CloneErrorCodes.NETWORKING,
              message: "Invalid networking",
              system_id: "def456",
            },
          ],
        },
        event: NodeActions.CLONE,
        id: machine.system_id,
      }),
    ];

    renderWithProviders(
      <CloneResults
        closeForm={vi.fn()}
        selectedCount={2}
        sourceMachine={machine}
      />,
      {
        initialEntries: [{ pathname: "/machines", key: "testKey" }],
        state,
      }
    );
    expect(screen.getByTestId("errors-table")).toBeInTheDocument();
    // +1 row due to the header
    expect(screen.getAllByRole("row").length).toBe(3);
  });

  it("can filter machines by error type", async () => {
    const setSearchFilter = vi.fn();
    state.machine.eventErrors = [
      factory.machineEventError({
        error: {
          destinations: [
            {
              code: CloneErrorCodes.NETWORKING,
              message: "Invalid networking",
              system_id: "def456",
            },
            {
              code: CloneErrorCodes.NETWORKING,
              message: "Invalid networking",
              system_id: "ghi789",
            },
          ],
        },
        event: NodeActions.CLONE,
        id: machine.system_id,
      }),
    ];

    renderWithProviders(
      <CloneResults
        closeForm={vi.fn()}
        setSearchFilter={setSearchFilter}
        sourceMachine={machine}
      />,
      {
        initialEntries: [{ pathname: "/machines", key: "testKey" }],
        state,
      }
    );
    await userEvent.click(screen.getByTestId("error-filter-link"));
    expect(setSearchFilter).toHaveBeenCalledWith("system_id:(def456,ghi789)");
  });

  it("does not show filter links if viewing from machine details", () => {
    const setSearchFilter = vi.fn();
    state.machine.eventErrors = [
      factory.machineEventError({
        error: {
          destinations: [
            {
              code: CloneErrorCodes.NETWORKING,
              message: "Invalid networking",
              system_id: "def456",
            },
            {
              code: CloneErrorCodes.NETWORKING,
              message: "Invalid networking",
              system_id: "ghi789",
            },
          ],
        },
        event: NodeActions.CLONE,
        id: machine.system_id,
      }),
    ];

    renderWithProviders(
      <CloneResults
        closeForm={vi.fn()}
        setSearchFilter={setSearchFilter}
        sourceMachine={machine}
        viewingDetails
      />,
      {
        initialEntries: [{ pathname: "/machine/abc123", key: "testKey" }],
        state,
      }
    );
    expect(screen.queryByTestId("error-filter-link")).not.toBeInTheDocument();
  });
});
