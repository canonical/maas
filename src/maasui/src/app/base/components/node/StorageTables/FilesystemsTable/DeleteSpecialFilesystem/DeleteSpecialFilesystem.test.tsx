import DeleteSpecialFilesystem from "./DeleteSpecialFilesystem";

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
    <DeleteSpecialFilesystem
      mountPoint={filesystem.mount_point}
      systemId="abc123"
    />,
    { state }
  );

  expect(
    screen.getByRole("form", { name: "Delete special filesystem" })
  ).toBeInTheDocument();
});

it("can remove a special filesystem", async () => {
  const { store } = renderWithProviders(
    <DeleteSpecialFilesystem
      mountPoint={filesystem.mount_point}
      systemId="abc123"
    />,
    { state }
  );

  expect(
    screen.getByRole("form", { name: "Delete special filesystem" })
  ).toBeInTheDocument();
  expect(
    screen.getByText("Are you sure you want to remove this special filesystem?")
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Remove" }));
  const expectedAction = machineActions.unmountSpecial({
    mountPoint: filesystem.mount_point,
    systemId: machine.system_id,
  });

  expect(
    store.getActions().find((action) => action.type === expectedAction.type)
  ).toStrictEqual(expectedAction);
});
