import CreateBcache from "./CreateBcache";

import { MIN_PARTITION_SIZE } from "@/app/store/machine/constants";
import { BcacheModes } from "@/app/store/machine/types";
import { DiskTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("CreateBcache", () => {
  it("sets the initial name correctly", () => {
    const cacheSet = factory.nodeDisk({ type: DiskTypes.CACHE_SET });
    const bcaches = [
      factory.nodeDisk({
        name: "bcache0",
        parent: {
          id: 0,
          type: DiskTypes.BCACHE,
          uuid: "bcache0",
        },
        type: DiskTypes.VIRTUAL,
      }),
      factory.nodeDisk({
        name: "bcache1",
        parent: {
          id: 1,
          type: DiskTypes.BCACHE,
          uuid: "bcache1",
        },
        type: DiskTypes.VIRTUAL,
      }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            disks: [cacheSet, ...bcaches],
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });

    renderWithProviders(
      <CreateBcache storageDevice={factory.nodeDisk()} systemId="abc123" />,
      { state }
    );

    // Two bcaches already exist so the next one should be bcache2
    expect(screen.getByRole("textbox", { name: /name/i })).toHaveValue(
      "bcache2"
    );
  });

  it("correctly dispatches an action to create a bcache", async () => {
    const cacheSet = factory.nodeDisk({ type: DiskTypes.CACHE_SET });
    const backingDevice = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      type: DiskTypes.PHYSICAL,
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            disks: [backingDevice, cacheSet],
            system_id: "abc123",
            supported_filesystems: [{ key: "fat32", ui: "FAT32" }],
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    const { store } = renderWithProviders(
      <CreateBcache storageDevice={backingDevice} systemId="abc123" />,
      { state }
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /cache set/i }),
      cacheSet.id.toString()
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /cache mode/i }),
      BcacheModes.WRITE_BACK
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /filesystem/i }),
      "fat32"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /mount options/i }),
      "noexec"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /mount point/i }),
      "/path"
    );
    await userEvent.click(
      screen.getByRole("button", { name: /create bcache/i })
    );

    expect(
      store
        .getActions()
        .find((action) => action.type === "machine/createBcache")
    ).toStrictEqual({
      meta: {
        method: "create_bcache",
        model: "machine",
      },
      payload: {
        params: {
          block_id: backingDevice.id,
          cache_mode: BcacheModes.WRITE_BACK,
          cache_set: cacheSet.id,
          fstype: "fat32",
          mount_options: "noexec",
          mount_point: "/path",
          name: "bcache0",
          system_id: "abc123",
        },
      },
      type: "machine/createBcache",
    });
  });
});
