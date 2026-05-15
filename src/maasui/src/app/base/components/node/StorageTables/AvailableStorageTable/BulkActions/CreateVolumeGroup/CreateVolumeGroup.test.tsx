import CreateVolumeGroup from "./CreateVolumeGroup";

import { DiskTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  within,
} from "@/testing/utils";

describe("CreateVolumeGroupForm", () => {
  describe("CreateVolumeGroupForm Table", () => {
    const [selectedDisk, selectedPartition] = [
      factory.nodeDisk({
        name: "floppy",
        partitions: null,
        type: DiskTypes.PHYSICAL,
      }),
      factory.nodePartition({ filesystem: null, name: "flippy" }),
    ];
    const disks = [
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
    it("displays the columns correctly", () => {
      renderWithProviders(
        <CreateVolumeGroup selected={[]} systemId="abc123" />,
        { state }
      );
      ["Name", "Size", "Device Type"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });
    it("shows the details of the selected storage devices in the table", () => {
      renderWithProviders(
        <CreateVolumeGroup
          selected={[selectedDisk, selectedPartition]}
          systemId="abc123"
        />,
        { state }
      );

      const rows = screen.getAllByRole("row");
      expect(rows).toHaveLength(3);
      expect(within(rows[1]).getAllByRole("cell")[0]).toHaveTextContent(
        selectedDisk.name
      );
      expect(within(rows[2]).getAllByRole("cell")[0]).toHaveTextContent(
        selectedPartition.name
      );
      expect(screen.getByText(new RegExp(selectedPartition.name, "i")));
    });
  });
  describe("CreateVolumeGroupForm Details and Actions", () => {
    it("sets the initial name correctly", () => {
      const vgs = [
        factory.nodeDisk({ type: DiskTypes.VOLUME_GROUP }),
        factory.nodeDisk({ type: DiskTypes.VOLUME_GROUP }),
      ];
      const physicalDisk = factory.nodeDisk({
        partitions: null,
        type: DiskTypes.PHYSICAL,
      });
      const state = factory.rootState({
        machine: factory.machineState({
          items: [
            factory.machineDetails({
              disks: [...vgs, physicalDisk],
              system_id: "abc123",
            }),
          ],
          statuses: factory.machineStatuses({
            abc123: factory.machineStatus(),
          }),
        }),
      });
      renderWithProviders(
        <CreateVolumeGroup selected={[physicalDisk]} systemId="abc123" />,
        { state }
      );

      // Two volume groups already exist so the next one should be vg2
      expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("vg2");
    });

    it("correctly dispatches an action to create a volume group", async () => {
      const [selectedDisk, selectedPartition] = [
        factory.nodeDisk({ partitions: null, type: DiskTypes.PHYSICAL }),
        factory.nodePartition({ filesystem: null }),
      ];
      const disks = [
        selectedDisk,
        factory.nodeDisk({ partitions: [selectedPartition] }),
      ];
      const state = factory.rootState({
        machine: factory.machineState({
          items: [
            factory.machineDetails({ disks: disks, system_id: "abc123" }),
          ],
          statuses: factory.machineStatuses({
            abc123: factory.machineStatus(),
          }),
        }),
      });
      const { store } = renderWithProviders(
        <CreateVolumeGroup
          selected={[selectedDisk, selectedPartition]}
          systemId="abc123"
        />,
        { state }
      );

      await userEvent.click(
        screen.getByRole("button", { name: "Create volume group" })
      );

      expect(
        store
          .getActions()
          .find((action) => action.type === "machine/createVolumeGroup")
      ).toEqual({
        meta: {
          method: "create_volume_group",
          model: "machine",
        },
        payload: {
          params: {
            block_devices: [selectedDisk.id],
            name: "vg0",
            partitions: [selectedPartition.id],
            system_id: "abc123",
          },
        },
        type: "machine/createVolumeGroup",
      });
    });
  });
});
