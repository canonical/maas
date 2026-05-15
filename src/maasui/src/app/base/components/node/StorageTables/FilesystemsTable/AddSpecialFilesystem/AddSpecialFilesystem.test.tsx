import AddSpecialFilesystem from "./AddSpecialFilesystem";

import { machineActions } from "@/app/store/machine";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

it("only shows filesystems that do not require a storage device", () => {
  const machine = factory.machineDetails({
    supported_filesystems: [
      { key: "fat32", ui: "fat32" }, // requires storage
      { key: "ramfs", ui: "ramfs" }, // does not require storage
    ],
    system_id: "abc123",
  });
  const state = factory.rootState({
    machine: factory.machineState({
      items: [machine],
      statuses: factory.machineStatuses({
        [machine.system_id]: factory.machineStatus(),
      }),
    }),
  });
  renderWithProviders(<AddSpecialFilesystem machine={machine} />, { state });

  expect(screen.getByRole("option", { name: "ramfs" })).toBeInTheDocument();
  expect(
    screen.queryByRole("option", { name: "fat32" })
  ).not.toBeInTheDocument();
});

it("can show errors", () => {
  const machine = factory.machineDetails({ system_id: "abc123" });
  const state = factory.rootState({
    machine: factory.machineState({
      eventErrors: [
        factory.machineEventError({
          error: "you can't do that",
          event: "mountSpecial",
          id: machine.system_id,
        }),
      ],
      items: [machine],
      statuses: factory.machineStatuses({
        [machine.system_id]: factory.machineStatus(),
      }),
    }),
  });
  renderWithProviders(<AddSpecialFilesystem machine={machine} />, { state });

  expect(screen.getByText("you can't do that")).toBeInTheDocument();
});

it("correctly dispatches an action to mount a special filesystem", async () => {
  const machine = factory.machineDetails({
    supported_filesystems: [{ key: "ramfs", ui: "ramfs" }],
    system_id: "abc123",
  });
  const state = factory.rootState({
    machine: factory.machineState({
      items: [machine],
      statuses: factory.machineStatuses({
        [machine.system_id]: factory.machineStatus(),
      }),
    }),
  });
  const { store } = renderWithProviders(
    <AddSpecialFilesystem machine={machine} />,
    { state }
  );

  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Type" }),
    "ramfs"
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: "Mount point" }),
    "/abc"
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: "Mount options" }),
    "qwerty"
  );
  await userEvent.click(screen.getByRole("button", { name: "Mount" }));

  await waitFor(() => {
    const expectedAction = machineActions.mountSpecial({
      fstype: "ramfs",
      mountOptions: "qwerty",
      mountPoint: "/abc",
      systemId: machine.system_id,
    });
    expect(
      store.getActions().find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });
});
