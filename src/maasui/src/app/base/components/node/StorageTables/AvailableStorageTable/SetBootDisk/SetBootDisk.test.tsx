import SetBootDisk from "./SetBootDisk";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

const disk = factory.nodeDisk({
  id: 1,
  name: "floppy-disk",
  partitions: [factory.nodePartition(), factory.nodePartition()],
});

const state = factory.rootState({
  machine: factory.machineState({
    items: [factory.machineDetails({ disks: [disk], system_id: "abc123" })],
    statuses: factory.machineStatuses({
      abc123: factory.machineStatus(),
    }),
  }),
});

it("should render the form", () => {
  renderWithProviders(<SetBootDisk diskId={disk.id} systemId="abc123" />, {
    state,
  });

  expect(
    screen.getByRole("form", { name: "Set boot disk" })
  ).toBeInTheDocument();
});

it("should fire an action to set boot disk", async () => {
  const { store } = renderWithProviders(
    <SetBootDisk diskId={disk.id} systemId="abc123" />,
    {
      state,
    }
  );

  await userEvent.click(screen.getByRole("button", { name: "Set boot disk" }));

  expect(
    store.getActions().some((action) => action.type === "machine/setBootDisk")
  ).toBe(true);
});
