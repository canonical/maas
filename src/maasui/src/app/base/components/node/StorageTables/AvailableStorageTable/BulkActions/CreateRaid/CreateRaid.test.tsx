import CreateRaid from "./CreateRaid";

import { DiskTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("CreateRaid", () => {
  it("sets the initial name correctly", () => {
    const physicalDisk = factory.nodeDisk({
      partitions: null,
      type: DiskTypes.PHYSICAL,
    });
    const raids = [
      factory.nodeDisk({
        parent: { id: 123, type: DiskTypes.RAID_0, uuid: "md0" },
        type: DiskTypes.VIRTUAL,
      }),
      factory.nodeDisk({
        parent: { id: 123, type: DiskTypes.RAID_10, uuid: "md1" },
        type: DiskTypes.VIRTUAL,
      }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            disks: [...raids, physicalDisk],
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });

    renderWithProviders(
      <CreateRaid selected={[physicalDisk]} systemId="abc123" />,
      { state }
    );

    expect(screen.getByRole("textbox", { name: /name/i })).toHaveValue("md2");
  });

  it("correctly dispatches an action to create a RAID device", async () => {
    const [selectedDisk, selectedPartition] = [
      factory.nodeDisk({ id: 9, partitions: null, type: DiskTypes.PHYSICAL }),
      factory.nodePartition({ id: 10, filesystem: null }),
    ];
    const disks = [
      selectedDisk,
      factory.nodeDisk({ partitions: [selectedPartition] }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            disks,
            system_id: "abc123",
            supported_filesystems: [{ key: "ext4", ui: "ext4" }],
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    const { store } = renderWithProviders(
      <CreateRaid
        selected={[selectedDisk, selectedPartition]}
        systemId="abc123"
      />,
      { state }
    );

    await userEvent.clear(screen.getByRole("textbox", { name: "Name" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "md1");
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "RAID level" }),
      "raid-1"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Filesystem" }),
      "ext4"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Mount point" }),
      "/mount-point"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Mount options" }),
      "option1,option2"
    );
    await userEvent.click(screen.getByRole("button", { name: /Create RAID/i }));

    expect(
      store.getActions().find((action) => action.type === "machine/createRaid")
    ).toStrictEqual({
      meta: {
        method: "create_raid",
        model: "machine",
      },
      payload: {
        params: {
          block_devices: [selectedDisk.id],
          fstype: "ext4",
          level: "raid-1",
          mount_options: "option1,option2",
          mount_point: "/mount-point",
          name: "md1",
          partitions: [selectedPartition.id],
          system_id: "abc123",
          tags: [],
        },
      },
      type: "machine/createRaid",
    });
  });
});
