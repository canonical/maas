import EditPartition from "./EditPartition";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("EditPartition", () => {
  it("can show errors", () => {
    const partition = factory.nodePartition();
    const disk = factory.nodeDisk({ partitions: [partition] });
    const state = factory.rootState({
      machine: factory.machineState({
        eventErrors: [
          {
            error: "didn't work",
            event: "updateFilesystem",
            id: "abc123",
          },
        ],
        items: [factory.machineDetails({ disks: [disk], system_id: "abc123" })],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(
      <EditPartition disk={disk} partition={partition} systemId="abc123" />,
      { state }
    );

    expect(screen.getByText(/didn't work/i)).toBeInTheDocument();
  });

  it("correctly dispatches an action to edit a partition", async () => {
    const partition = factory.nodePartition();
    const disk = factory.nodeDisk({ partitions: [partition] });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            disks: [disk],
            supported_filesystems: [{ key: "fat32", ui: "FAT32" }],
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    const { store } = renderWithProviders(
      <EditPartition disk={disk} partition={partition} systemId="abc123" />,
      { state }
    );

    await userEvent.selectOptions(
      screen.getByLabelText(/filesystem/i),
      "fat32"
    );
    await userEvent.type(screen.getByLabelText(/mount options/i), "noexec");
    await userEvent.type(screen.getByLabelText(/mount point/i), "/path");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(
      store
        .getActions()
        .find((action) => action.type === "machine/updateFilesystem")
    ).toEqual({
      meta: {
        method: "update_filesystem",
        model: "machine",
      },
      payload: {
        params: {
          block_id: disk.id,
          partition_id: partition.id,
          fstype: "fat32",
          mount_options: "noexec",
          mount_point: "/path",
          system_id: "abc123",
        },
      },
      type: "machine/updateFilesystem",
    });
  });
});
