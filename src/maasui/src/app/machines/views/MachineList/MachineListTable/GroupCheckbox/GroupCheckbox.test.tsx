import GroupCheckbox from "./GroupCheckbox";

import { machineActions } from "@/app/store/machine";
import { FetchGroupKey } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

let state: RootState;
const callId = "123456";
const group = factory.machineStateListGroup({
  count: 2,
  name: "admin2",
  value: "admin-2",
  items: ["machine1", "machine2", "machine3"],
});
beforeEach(() => {
  state = factory.rootState({
    machine: factory.machineState({
      lists: {
        [callId]: factory.machineStateList({
          groups: [group],
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
    <GroupCheckbox
      callId={callId}
      group={group}
      groupName="admin2"
      grouping={FetchGroupKey.AgentName}
    />,
    {
      state,
    }
  );
  expect(screen.getByRole("checkbox")).toBeDisabled();
});

it("is disabled if there are no machines in the group", () => {
  const group = factory.machineStateListGroup({
    count: 0,
    name: "admin2",
    value: "admin-2",
  });
  state.machine.lists[callId].groups = [group];
  renderWithProviders(
    <GroupCheckbox
      callId={callId}
      group={group}
      groupName="admin2"
      grouping={FetchGroupKey.AgentName}
    />,
    {
      state,
    }
  );
  expect(screen.getByRole("checkbox")).toBeDisabled();
});

it("is not disabled if there are machines in the group", () => {
  state.machine.lists[callId].groups = [
    factory.machineStateListGroup({
      count: 1,
      name: "admin2",
      value: "admin-2",
    }),
  ];
  renderWithProviders(
    <GroupCheckbox
      callId={callId}
      group={group}
      groupName="admin2"
      grouping={FetchGroupKey.AgentName}
    />,
    {
      state,
    }
  );
  expect(screen.getByRole("checkbox")).not.toBeDisabled();
});

it("is unchecked if there are no filters, groups or items selected", () => {
  state.machine.selected = null;
  renderWithProviders(
    <GroupCheckbox
      callId={callId}
      group={group}
      groupName="admin2"
      grouping={FetchGroupKey.AgentName}
    />,
    {
      state,
    }
  );
  expect(screen.getByRole("checkbox")).not.toBeChecked();
});

it("is checked if all machines are selected", () => {
  state.machine.selected = {
    filter: {
      owner: "admin",
    },
  };
  renderWithProviders(
    <GroupCheckbox
      callId={callId}
      group={group}
      groupName="admin2"
      grouping={FetchGroupKey.AgentName}
    />,
    {
      state,
    }
  );
  expect(screen.getByRole("checkbox")).toBeChecked();
});

it("is checked if the group is selected", () => {
  state.machine.selected = {
    items: ["machine1", "machine2", "machine3"],
  };
  renderWithProviders(
    <GroupCheckbox
      callId={callId}
      group={group}
      groupName="admin2"
      grouping={FetchGroupKey.AgentName}
    />,
    {
      state,
    }
  );
  expect(screen.getByRole("checkbox")).toBeChecked();
});

it("is partially checked if a machine in the group is selected", () => {
  const group = factory.machineStateListGroup({
    count: 2,
    items: ["abc123", "def456"],
    name: "admin2",
    value: "admin-2",
  });
  state.machine.lists[callId].groups = [group];
  state.machine.selected = {
    items: ["abc123"],
  };
  renderWithProviders(
    <GroupCheckbox
      callId={callId}
      group={group}
      groupName="admin2"
      grouping={FetchGroupKey.AgentName}
    />,
    {
      state,
    }
  );
  expect(screen.getByRole("checkbox")).toBePartiallyChecked();
});

it("is not checked if a selected machine is in another group", () => {
  const group = factory.machineStateListGroup({
    count: 2,
    items: ["abc123"],
    name: "admin2",
    value: "admin-2",
  });
  state.machine.lists[callId].groups = [
    factory.machineStateListGroup({
      count: 2,
      items: ["def456"],
      name: "admin1",
    }),
    group,
  ];
  state.machine.selected = {
    items: ["def456"],
  };
  renderWithProviders(
    <GroupCheckbox
      callId={callId}
      group={group}
      groupName="admin2"
      grouping={FetchGroupKey.AgentName}
    />,
    {
      state,
    }
  );
  expect(screen.getByRole("checkbox")).not.toBeChecked();
});

it("can dispatch an action to select the group", async () => {
  const { store } = renderWithProviders(
    <GroupCheckbox
      callId={callId}
      group={group}
      groupName="admin2"
      grouping={FetchGroupKey.AgentName}
    />,
    { state }
  );

  await userEvent.click(screen.getByRole("checkbox"));

  const expected = machineActions.setSelected({
    grouping: FetchGroupKey.AgentName,
    items: ["machine1", "machine2", "machine3"],
  });

  expect(
    store.getActions().find((action) => action.type === expected.type)
  ).toStrictEqual(expected);
});

it("does not overwrite selected machines in different groups", async () => {
  const group = factory.machineStateListGroup({
    count: 2,
    items: ["abc123"],
    name: "admin2",
    value: "admin-2",
  });
  state.machine.lists[callId].groups = [
    factory.machineStateListGroup({
      count: 2,
      items: ["def456"],
      name: "admin1",
    }),
    group,
  ];
  state.machine.selected = {
    items: ["def456"],
  };

  const { store } = renderWithProviders(
    <GroupCheckbox
      callId={callId}
      group={group}
      groupName="admin2"
      grouping={FetchGroupKey.AgentName}
    />,
    { state }
  );

  await userEvent.click(screen.getByRole("checkbox"));

  const expected = machineActions.setSelected({
    grouping: FetchGroupKey.AgentName,
    items: ["def456", "abc123"],
  });

  expect(
    store.getActions().find((action) => action.type === expected.type)
  ).toStrictEqual(expected);
});

it("can dispatch an action to unselect the group", async () => {
  const group = factory.machineStateListGroup({
    count: 2,
    items: ["abc123"],
    name: "admin2",
    value: "admin-2",
  });
  state.machine.lists[callId].groups = [
    factory.machineStateListGroup({
      count: 2,
      items: ["def456"],
      name: "admin1",
      value: "admin-1",
    }),
    group,
  ];
  state.machine.selected = {
    items: ["def456", "abc123"],
  };

  const { store } = renderWithProviders(
    <GroupCheckbox
      callId={callId}
      group={group}
      groupName="admin2"
      grouping={FetchGroupKey.AgentName}
    />,
    { state }
  );

  await userEvent.click(screen.getByRole("checkbox"));

  const expected = machineActions.setSelected({
    items: ["def456"],
  });

  expect(
    store.getActions().find((action) => action.type === expected.type)
  ).toStrictEqual(expected);
});

it("can dispatch an action to unselect the group when it's partially selected", async () => {
  const group = factory.machineStateListGroup({
    count: 2,
    items: ["abc123", "ghi789"],
    name: "admin2",
    value: "admin-2",
  });
  state.machine.lists[callId].groups = [
    factory.machineStateListGroup({
      count: 2,
      items: ["def456"],
      name: "admin1",
      value: "admin-1",
    }),
    group,
  ];
  state.machine.selected = {
    items: ["def456", "abc123"],
  };

  const { store } = renderWithProviders(
    <GroupCheckbox
      callId={callId}
      group={group}
      groupName="admin2"
      grouping={FetchGroupKey.AgentName}
    />,
    { state }
  );

  await userEvent.click(screen.getByRole("checkbox"));

  const expected = machineActions.setSelected({
    items: ["def456"],
  });

  expect(
    store.getActions().find((action) => action.type === expected.type)
  ).toStrictEqual(expected);
});
