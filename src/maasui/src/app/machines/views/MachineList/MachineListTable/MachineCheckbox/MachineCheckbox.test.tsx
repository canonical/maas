import MachineCheckbox, { getSelectedMachinesRange } from "./MachineCheckbox";

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
        [callId]: factory.machineStateList({
          groups: [
            factory.machineStateListGroup({
              count: 1,
              items: ["abc123"],
              name: "admin2",
            }),
          ],
        }),
      },
    }),
  });
});

it("is disabled if all machines are selected", () => {
  state.machine.selected = {
    filter: {
      owner: "admin",
    },
  };
  renderWithProviders(
    <MachineCheckbox
      callId={callId}
      groupValue="admin2"
      label="spotted-handfish"
      systemId="abc123"
    />,
    { state }
  );
  expect(screen.getByRole("checkbox")).toBeDisabled();
});

it("is checked and disabled if the machine's group is selected", () => {
  state.machine.selected = {
    groups: ["admin2"],
  };
  renderWithProviders(
    <MachineCheckbox
      callId={callId}
      groupValue="admin2"
      label="spotted-handfish"
      systemId="abc123"
    />,
    { state }
  );
  expect(screen.getByRole("checkbox")).toBeDisabled();
  expect(screen.getByRole("checkbox")).toBeChecked();
});

it("is checked and disabled if the machine's group is selected and is nullish", () => {
  state.machine.selected = {
    groups: [""],
  };
  renderWithProviders(
    <MachineCheckbox
      callId={callId}
      groupValue=""
      label="spotted-handfish"
      systemId="abc123"
    />,
    { state }
  );
  expect(screen.getByRole("checkbox")).toBeDisabled();
  expect(screen.getByRole("checkbox")).toBeChecked();
});

it("is unchecked and enabled if there are no filters or groups selected", () => {
  state.machine.selected = null;
  renderWithProviders(
    <MachineCheckbox
      callId={callId}
      groupValue="admin2"
      label="spotted-handfish"
      systemId="abc123"
    />,
    { state }
  );
  expect(screen.getByRole("checkbox")).not.toBeChecked();
  expect(screen.getByRole("checkbox")).not.toBeDisabled();
});

it("is checked if the machine is selected", () => {
  state.machine.selected = {
    items: ["abc123"],
  };
  renderWithProviders(
    <MachineCheckbox
      callId={callId}
      groupValue="admin2"
      label="spotted-handfish"
      systemId="abc123"
    />,
    { state }
  );
  expect(screen.getByRole("checkbox")).toBeChecked();
});

it("can dispatch an action to select the machine", async () => {
  const { store } = renderWithProviders(
    <MachineCheckbox
      callId={callId}
      groupValue="admin2"
      label="spotted-handfish"
      systemId="abc123"
    />,
    { state }
  );
  await userEvent.click(screen.getByRole("checkbox"));
  const expected = machineActions.setSelected({ items: ["abc123"] });
  expect(
    store.getActions().find((action) => action.type === expected.type)
  ).toStrictEqual(expected);
});

it("can dispatch an action to unselect a machine", async () => {
  state.machine.selected = {
    groups: ["admin1"],
    items: ["abc123", "def456"],
  };

  const { store } = renderWithProviders(
    <MachineCheckbox
      callId={callId}
      groupValue="admin2"
      label="spotted-handfish"
      systemId="abc123"
    />,
    { state }
  );
  await userEvent.click(screen.getByRole("checkbox"));
  const expected = machineActions.setSelected({
    groups: ["admin1"],
    items: ["def456"],
  });
  expect(
    store.getActions().find((action) => action.type === expected.type)
  ).toStrictEqual(expected);
});

describe("getSelectedMachinesRange tests", () => {
  const systemIds = [
    "system_id_1",
    "system_id_2",
    "system_id_3",
    "system_id_4",
  ];
  const machines = systemIds.map((id) => factory.machine({ system_id: id }));

  it("getSelectedMachinesRange selects a range of machines", () => {
    const selected = { groups: [""], items: [systemIds[0]] };
    const systemId = systemIds.at(-1)!;

    const newSelected = getSelectedMachinesRange({
      systemId,
      machines,
      selected: selected,
    });

    expect(newSelected.items?.sort()).toStrictEqual(systemIds.sort());
  });

  it("Selects only one machine if there's no previously selected machine", () => {
    const systemId = systemIds[0];
    const selected = { groups: [""], items: [] };

    const newSelected = getSelectedMachinesRange({
      systemId,
      machines,
      selected: selected,
    });
    const { items } = newSelected;
    expect(items?.length).toBe(1);
    expect(items![0]).toBe(systemId);
  });
});
