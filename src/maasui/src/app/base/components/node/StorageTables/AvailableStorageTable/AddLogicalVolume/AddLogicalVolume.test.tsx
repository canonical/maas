import AddLogicalVolume from "./AddLogicalVolume";

import { MIN_PARTITION_SIZE } from "@/app/store/machine/constants";
import { DiskTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders, userEvent, screen } from "@/testing/utils";

describe("AddLogicalVolume", () => {
  it("sets the initial name correctly", () => {
    const volumeGroup = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      name: "voldemort",
      type: DiskTypes.VOLUME_GROUP,
    });
    const logicalVolumes = [
      factory.nodeDisk({
        name: "lv0",
        parent: {
          id: volumeGroup.id,
          uuid: volumeGroup.name,
          type: volumeGroup.type,
        },
        type: DiskTypes.VIRTUAL,
      }),
      factory.nodeDisk({
        name: "lv1",
        parent: {
          id: volumeGroup.id,
          uuid: volumeGroup.name,
          type: volumeGroup.type,
        },
        type: DiskTypes.VIRTUAL,
      }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            disks: [volumeGroup, ...logicalVolumes],
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(
      <AddLogicalVolume disk={volumeGroup} systemId="abc123" />,
      { state }
    );

    // Two logical volumes already exist so the next one should be lv2
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("lv2");
  });

  it("sets the initial size to the available space", () => {
    const volumeGroup = factory.nodeDisk({
      available_size: 8000000000,
      name: "voldemort",
      type: DiskTypes.VOLUME_GROUP,
    });
    const logicalVolumes = [
      factory.nodeDisk({
        name: "lv0",
        parent: {
          id: volumeGroup.id,
          uuid: volumeGroup.name,
          type: volumeGroup.type,
        },
        type: DiskTypes.VIRTUAL,
      }),
      factory.nodeDisk({
        name: "lv1",
        parent: {
          id: volumeGroup.id,
          uuid: volumeGroup.name,
          type: volumeGroup.type,
        },
        type: DiskTypes.VIRTUAL,
      }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            disks: [volumeGroup, ...logicalVolumes],
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(
      <AddLogicalVolume disk={volumeGroup} systemId="abc123" />,
      { state }
    );

    expect(screen.getByRole("spinbutton", { name: "Size" })).toHaveValue(8);
    expect(screen.getByLabelText("Unit")).toHaveValue("GB");
  });

  it("can validate if the size meets the minimum requirement", async () => {
    const disk = factory.nodeDisk({
      available_size: 1000000000, // 1GB
      id: 1,
      type: DiskTypes.VOLUME_GROUP,
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ disks: [disk], system_id: "abc123" })],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(<AddLogicalVolume disk={disk} systemId="abc123" />, {
      state,
    });

    // Set logical volume size to 0.1MB
    await userEvent.clear(screen.getByRole("spinbutton", { name: "Size" }));
    await userEvent.type(
      screen.getByRole("spinbutton", { name: "Size" }),
      "0.1"
    );
    await userEvent.selectOptions(screen.getByLabelText("Unit"), "MB");
    expect(
      screen.getByText(/At least 4.19MB is required to add a logical volume/i)
    ).toBeInTheDocument();
  });

  it("can validate if the size is less than available disk space", async () => {
    const disk = factory.nodeDisk({
      available_size: 1000000000, // 1GB
      id: 1,
      type: DiskTypes.VOLUME_GROUP,
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ disks: [disk], system_id: "abc123" })],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(<AddLogicalVolume disk={disk} systemId="abc123" />, {
      state,
    });

    // Set logical volume size to 2GB
    await userEvent.clear(screen.getByRole("spinbutton", { name: "Size" }));
    await userEvent.type(screen.getByRole("spinbutton", { name: "Size" }), "2");
    expect(
      screen.getByText(/Only 1GB available in this volume group/i)
    ).toBeInTheDocument();
  });

  it("correctly dispatches an action to create a logical volume", async () => {
    const disk = factory.nodeDisk({
      available_size: 20000000000,
      id: 1,
      type: DiskTypes.VOLUME_GROUP,
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            disks: [disk],
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
      <AddLogicalVolume disk={disk} systemId="abc123" />,
      {
        state,
      }
    );

    await userEvent.clear(screen.getByRole("spinbutton", { name: "Size" }));
    await userEvent.type(
      screen.getByRole("spinbutton", { name: "Size" }),
      "10"
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Filesystem" }),
      "fat32"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Mount point" }),
      "/path"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Mount options" }),
      "noexec"
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Add logical volume" })
    );

    expect(
      store
        .getActions()
        .find((action) => action.type === "machine/createLogicalVolume")
    ).toStrictEqual({
      meta: {
        method: "create_logical_volume",
        model: "machine",
      },
      payload: {
        params: {
          fstype: "fat32",
          mount_options: "noexec",
          mount_point: "/path",
          name: "lv0",
          size: 10000000000,
          system_id: "abc123",
          volume_group_id: 1,
        },
      },
      type: "machine/createLogicalVolume",
    });
  });
});
