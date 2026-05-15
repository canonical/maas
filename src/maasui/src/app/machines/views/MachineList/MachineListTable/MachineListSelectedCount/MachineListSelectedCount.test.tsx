import MachineListSelectedCount from "./MachineListSelectedCount";

import { machineActions } from "@/app/store/machine";
import type { RootState } from "@/app/store/root/types";
import {
  screen,
  renderWithProviders,
  getTestState,
  userEvent,
} from "@/testing/utils";

describe("MachineListSelectedCount", () => {
  let state: RootState;
  beforeEach(() => {
    state = getTestState();
  });

  it("displays the number of selected machines", () => {
    renderWithProviders(
      <MachineListSelectedCount
        filter={""}
        machineCount={20}
        selectedCount={10}
      />,
      { state }
    );

    expect(screen.getByText(/10 machines selected/i)).toBeInTheDocument();
  });

  it("displays a button to select all machines", () => {
    renderWithProviders(
      <MachineListSelectedCount
        filter={""}
        machineCount={20}
        selectedCount={10}
      />,
      { state }
    );

    expect(screen.getByRole("button")).toHaveTextContent(
      "Select all 20 machines"
    );
  });

  it("displays a button to select all filtered machines", () => {
    renderWithProviders(
      <MachineListSelectedCount
        filter={"filter"}
        machineCount={20}
        selectedCount={10}
      />,
      { state }
    );

    expect(screen.getByRole("button")).toHaveTextContent(
      "Select all 20 filtered machines"
    );
  });

  it("displays a button to clear selection if all machines are selected", () => {
    renderWithProviders(
      <MachineListSelectedCount
        filter={""}
        machineCount={20}
        selectedCount={20}
      />,
      { state }
    );

    expect(screen.getByText(/Selected all 20 machines/i)).toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveTextContent("Clear selection");
  });

  it("dispatches an action to select all machines", async () => {
    const { store } = renderWithProviders(
      <MachineListSelectedCount
        filter={""}
        machineCount={20}
        selectedCount={10}
      />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Select all 20 machines" })
    );

    const expectedAction = machineActions.setSelected({ filter: {} });

    expect(
      store.getActions().find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });

  it("dispatches an action to select all filtered machines", async () => {
    const { store } = renderWithProviders(
      <MachineListSelectedCount
        filter={"this-is-a-filter"}
        machineCount={20}
        selectedCount={10}
      />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Select all 20 filtered machines" })
    );

    const expectedAction = machineActions.setSelected({
      filter: { free_text: ["this-is-a-filter"] },
    });

    expect(
      store.getActions().find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });

  it("dispatches an action to clear the selection", async () => {
    const { store } = renderWithProviders(
      <MachineListSelectedCount
        filter={""}
        machineCount={20}
        selectedCount={20}
      />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Clear selection" })
    );

    const expectedAction = machineActions.setSelected(null);

    expect(
      store.getActions().find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });
});
