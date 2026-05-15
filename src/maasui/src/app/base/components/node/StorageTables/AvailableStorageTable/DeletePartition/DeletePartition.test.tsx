import DeletePartition from ".";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

const partition = factory.nodePartition();
const disk = factory.nodeDisk({
  id: 1,
  name: "floppy-disk",
  partitions: [partition, factory.nodePartition()],
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
  renderWithProviders(
    <DeletePartition partitionId={partition.id} systemId="abc123" />,
    { state }
  );

  expect(
    screen.getByRole("form", { name: "Delete partition" })
  ).toBeInTheDocument();
});

it("should fire an action to delete a partition", async () => {
  const { store } = renderWithProviders(
    <DeletePartition partitionId={partition.id} systemId="abc123" />,
    { state }
  );

  await userEvent.click(
    screen.getByRole("button", { name: "Remove partition" })
  );

  expect(
    store
      .getActions()
      .some((action) => action.type === "machine/deletePartition")
  ).toBe(true);
});
