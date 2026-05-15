import UnmountFilesystem from "./UnmountFilesystem";

import { machineActions } from "@/app/store/machine";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

const filesystem = factory.nodeFilesystem({ mount_point: "/disk-fs/path" });
const disk = factory.nodeDisk({ filesystem, partitions: [] });
const machine = factory.machineDetails({
  disks: [disk],
  system_id: "abc123",
});
const state = factory.rootState({
  machine: factory.machineState({
    items: [machine],
    statuses: factory.machineStatuses({
      abc123: factory.machineStatus(),
    }),
  }),
});

it("renders a delete confirmation form", () => {
  renderWithProviders(
    <UnmountFilesystem storageDevice={disk} systemId="abc123" />,

    { state }
  );

  expect(
    screen.getByRole("form", { name: "Unmount filesystem" })
  ).toBeInTheDocument();
  expect(
    screen.getByText("Are you sure you want to unmount this filesystem?")
  ).toBeInTheDocument();
});

it("can remove a special filesystem", async () => {
  const { store } = renderWithProviders(
    <UnmountFilesystem storageDevice={disk} systemId="abc123" />,
    { state }
  );

  await userEvent.click(screen.getByRole("button", { name: "Remove" }));
  const expectedAction = machineActions.updateFilesystem({
    blockId: disk.id,
    mountOptions: "",
    mountPoint: "",
    systemId: "abc123",
  });

  expect(
    store.getActions().find((action) => action.type === expectedAction.type)
  ).toStrictEqual(expectedAction);
});
