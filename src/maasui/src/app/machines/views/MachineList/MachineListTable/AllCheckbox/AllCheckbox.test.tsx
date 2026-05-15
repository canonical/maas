import AllCheckbox, { Label } from "./AllCheckbox";

import { machineActions } from "@/app/store/machine";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

let state: RootState;
const callId = "123456";

beforeEach(() => {
  state = factory.rootState({
    machine: factory.machineState({
      lists: {
        [callId]: factory.machineStateList(),
      },
    }),
  });
});

it("is unchecked if there are no filters, groups or items selected", () => {
  state.machine.selected = null;
  renderWithProviders(<AllCheckbox callId={callId} filter={null} />, { state });
  expect(
    screen.getByRole("checkbox", { name: Label.AllMachines })
  ).not.toBeChecked();
});

it("is checked if there is a selected filter", () => {
  state.machine.selected = {
    filter: {
      owner: "admin",
    },
  };
  renderWithProviders(<AllCheckbox callId={callId} filter={null} />, { state });
  expect(
    screen.getByRole("checkbox", { name: Label.AllMachines })
  ).toBeChecked();
});

it("is partially checked if a group is selected", () => {
  state.machine.selected = {
    groups: ["admin1"],
  };
  renderWithProviders(<AllCheckbox callId={callId} filter={null} />, { state });
  expect(
    screen.getByRole("checkbox", { name: Label.AllMachines })
  ).toBePartiallyChecked();
});

it("is partially checked if a machine is selected", () => {
  state.machine.selected = {
    items: ["abc123"],
  };
  renderWithProviders(<AllCheckbox callId={callId} filter={null} />, { state });
  expect(
    screen.getByRole("checkbox", { name: Label.AllMachines })
  ).toBePartiallyChecked();
});

it("can dispatch an action to select all", async () => {
  const filter = {
    owner: ["admin1"],
  };

  const { store } = renderWithProviders(
    <AllCheckbox callId={callId} filter={filter} />,
    {
      state,
    }
  );
  await userEvent.click(
    screen.getByRole("checkbox", { name: Label.AllMachines })
  );
  const expected = machineActions.setSelected({
    filter,
  });
  expect(
    store.getActions().find((action) => action.type === expected.type)
  ).toStrictEqual(expected);
});

it("can dispatch an action to unselect all", async () => {
  const filter = {
    owner: ["admin1"],
  };
  state.machine.selected = {
    filter,
  };

  const { store } = renderWithProviders(
    <AllCheckbox callId={callId} filter={filter} />,
    {
      state,
    }
  );
  await userEvent.click(
    screen.getByRole("checkbox", { name: Label.AllMachines })
  );
  const expected = machineActions.setSelected(null);
  expect(
    store.getActions().find((action) => action.type === expected.type)
  ).toStrictEqual(expected);
});
