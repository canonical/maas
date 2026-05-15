import UpdateDatastore from "./UpdateDatastore";

import { MIN_PARTITION_SIZE } from "@/app/store/machine/constants";
import { DiskTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("UpdateDatastore", () => {
  it("calculates the total size of the selected storage devices", () => {
    const [datastore, selectedDisk, selectedPartition] = [
      factory.nodeDisk({
        filesystem: factory.nodeFilesystem({ fstype: "vmfs6" }),
      }),
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        name: "floppy",
        partitions: null,
        size: 1000000000, // 1GB
        type: DiskTypes.PHYSICAL,
      }),
      factory.nodePartition({
        filesystem: null,
        name: "flippy",
        size: 500000000, // 500MB
      }),
    ];
    const disks = [
      datastore,
      selectedDisk,
      factory.nodeDisk({ partitions: [selectedPartition] }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ disks: disks, system_id: "abc123" })],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(
      <UpdateDatastore
        selected={[selectedDisk, selectedPartition]}
        systemId="abc123"
      />,
      { state }
    );

    expect(screen.getByTestId("size-to-add")).toHaveValue("1.5 GB");
  });

  it("correctly dispatches an action to update a datastore", async () => {
    const [datastore, selectedDisk, selectedPartition] = [
      factory.nodeDisk({
        filesystem: factory.nodeFilesystem({ fstype: "vmfs6" }),
      }),
      factory.nodeDisk({ partitions: null, type: DiskTypes.PHYSICAL }),
      factory.nodePartition({ filesystem: null }),
    ];
    const disks = [
      datastore,
      selectedDisk,
      factory.nodeDisk({ partitions: [selectedPartition] }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ disks: disks, system_id: "abc123" })],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    const { store } = renderWithProviders(
      <UpdateDatastore
        selected={[selectedDisk, selectedPartition]}
        systemId="abc123"
      />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Add to datastore" })
    );

    expect(
      store
        .getActions()
        .find((action) => action.type === "machine/updateVmfsDatastore")
    ).toStrictEqual({
      meta: {
        method: "update_vmfs_datastore",
        model: "machine",
      },
      payload: {
        params: {
          add_block_devices: [selectedDisk.id],
          add_partitions: [selectedPartition.id],
          system_id: "abc123",
          vmfs_datastore_id: datastore.id,
        },
      },
      type: "machine/updateVmfsDatastore",
    });
  });
});
