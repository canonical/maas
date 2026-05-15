import AvailableStorageTable from "./AvailableStorageTable";

import AddLogicalVolume from "@/app/base/components/node/StorageTables/AvailableStorageTable/AddLogicalVolume";
import AddPartition from "@/app/base/components/node/StorageTables/AvailableStorageTable/AddPartition";
import CreateBcache from "@/app/base/components/node/StorageTables/AvailableStorageTable/CreateBcache";
import CreateCacheSet from "@/app/base/components/node/StorageTables/AvailableStorageTable/CreateCacheSet";
import DeletePartition from "@/app/base/components/node/StorageTables/AvailableStorageTable/DeletePartition";
import DeleteVolumeGroup from "@/app/base/components/node/StorageTables/AvailableStorageTable/DeleteVolumeGroup";
import EditDisk from "@/app/base/components/node/StorageTables/AvailableStorageTable/EditDisk";
import EditPartition from "@/app/base/components/node/StorageTables/AvailableStorageTable/EditPartition";
import { MIN_PARTITION_SIZE } from "@/app/store/machine/constants";
import { DiskTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
  within,
} from "@/testing/utils";

const getAvailableDisk = (name = "available-disk") =>
  factory.nodeDisk({
    available_size: MIN_PARTITION_SIZE + 1,
    name,
    filesystem: null,
    type: DiskTypes.PHYSICAL,
  });

const { mockOpen } = await mockSidePanel();

describe("AvailableStorageTable", () => {
  describe("display", () => {
    it("can show an empty message", () => {
      const machine = factory.machineDetails({
        disks: [],
        system_id: "abc123",
      });
      const state = factory.rootState({
        machine: factory.machineState({
          items: [machine],
        }),
      });
      renderWithProviders(
        <AvailableStorageTable canEditStorage node={machine} />,
        {
          state,
        }
      );

      expect(
        screen.getByText("No available disks or partitions.")
      ).toBeInTheDocument();
    });

    it("only shows disks that are available", () => {
      const [availableDisk, usedDisk] = [
        getAvailableDisk(),
        factory.nodeDisk({
          available_size: MIN_PARTITION_SIZE - 1,
          filesystem: null,
          name: "used-disk",
          type: DiskTypes.PHYSICAL,
        }),
      ];
      const machine = factory.machineDetails({
        disks: [availableDisk, usedDisk],
        system_id: "abc123",
      });
      const state = factory.rootState({
        machine: factory.machineState({
          items: [machine],
        }),
      });
      renderWithProviders(
        <AvailableStorageTable canEditStorage node={machine} />,
        {
          state,
        }
      );

      const rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole(
        "row"
      );

      expect(rows).toHaveLength(1);

      // The first cell is the checkbox, so the second cell should have the name
      expect(within(rows[0]).getAllByRole("cell")[1]).toHaveTextContent(
        availableDisk.name
      );
    });

    it("does not show an action column, checkboxes or bulk actions if node is a controller", () => {
      const disk = getAvailableDisk();
      const controller = factory.controllerDetails({
        disks: [disk],
        system_id: "abc123",
      });
      const state = factory.rootState({
        controller: factory.controllerState({
          items: [controller],
        }),
      });
      renderWithProviders(
        <AvailableStorageTable canEditStorage node={controller} />,
        {
          state,
        }
      );

      expect(
        screen.queryByRole("columnheader", { name: "Actions" })
      ).not.toBeInTheDocument();
      expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Create volume group" })
      ).not.toBeInTheDocument();
    });

    it("show an action column, storage checkboxes and bulk actions if node is a machine", () => {
      const disk = getAvailableDisk();
      const machine = factory.machineDetails({
        disks: [disk],
        system_id: "abc123",
      });
      const state = factory.rootState({
        machine: factory.machineState({
          items: [machine],
        }),
      });
      renderWithProviders(
        <AvailableStorageTable canEditStorage node={machine} />,
        {
          state,
        }
      );

      expect(
        screen.getByRole("columnheader", { name: "Actions" })
      ).toBeInTheDocument();

      // A "select all" checkbox, and one more for the disk itself
      expect(screen.getAllByRole("checkbox")).toHaveLength(2);
      expect(
        screen.getByRole("button", { name: "Create volume group" })
      ).toBeInTheDocument();
    });
  });

  describe("actions", () => {
    it("disables action dropdown and checkboxes if storage cannot be edited", () => {
      const disk = getAvailableDisk();
      const machine = factory.machineDetails({
        disks: [disk],
        system_id: "abc123",
      });
      const state = factory.rootState({
        machine: factory.machineState({
          items: [machine],
        }),
      });
      renderWithProviders(
        <AvailableStorageTable canEditStorage={false} node={machine} />,
        {
          state,
        }
      );

      expect(
        screen.getByRole("button", { name: /Take action/ })
      ).toBeAriaDisabled();
      screen.getAllByRole("checkbox").forEach((checkbox) => {
        expect(checkbox).toBeDisabled();
      });
    });

    it("can open the add partition form if disk can be partitioned", async () => {
      const disk = getAvailableDisk();
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

      renderWithProviders(
        <AvailableStorageTable canEditStorage node={machine} />,
        {
          state,
        }
      );

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: /Add partition/ })
      );

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({ component: AddPartition })
      );
    });

    it("can trigger the edit partition form if partition can be edited", async () => {
      const partition = factory.nodePartition({ filesystem: null });
      const disk = factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE - 1,
        partitions: [partition],
      });
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

      renderWithProviders(
        <AvailableStorageTable canEditStorage node={machine} />,
        { state }
      );

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: /Edit partition/ })
      );

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: EditPartition,
        })
      );
    });

    it("can trigger the add logical volume form if disk can have one added", async () => {
      const disk = factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        type: DiskTypes.VOLUME_GROUP,
      });
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
      renderWithProviders(
        <AvailableStorageTable canEditStorage node={machine} />,
        { state }
      );

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: /Add logical volume/ })
      );

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: AddLogicalVolume,
        })
      );
    });

    it("can open the edit disk form if the disk is not a volume group", async () => {
      const disk = factory.nodeDisk({ type: DiskTypes.PHYSICAL });
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

      renderWithProviders(
        <AvailableStorageTable canEditStorage node={machine} />,
        { state }
      );

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: /Edit physical disk/ })
      );

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({ component: EditDisk })
      );
    });

    it("can open the create bcache form if the machine has at least one cache set", async () => {
      const backingDevice = factory.nodeDisk({ type: DiskTypes.PHYSICAL });
      const cacheSet = factory.nodeDisk({ type: DiskTypes.CACHE_SET });
      const machine = factory.machineDetails({
        disks: [backingDevice, cacheSet],
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
      renderWithProviders(
        <AvailableStorageTable canEditStorage node={machine} />,
        { state }
      );

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: /Create bcache/ })
      );

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: CreateBcache,
        })
      );
    });

    it("disables actions if a bulk action has been selected", async () => {
      const partitions = [
        factory.nodePartition({ filesystem: null, name: "part-1" }),
        factory.nodePartition({ filesystem: null, name: "part-2" }),
      ];
      const machine = factory.machineDetails({
        disks: [
          factory.nodeDisk({
            available_size: MIN_PARTITION_SIZE - 1,
            partitions: partitions,
            type: DiskTypes.PHYSICAL,
          }),
        ],
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
      const { rerender } = renderWithProviders(
        <AvailableStorageTable canEditStorage node={machine} />,
        { state }
      );

      await userEvent.click(screen.getAllByRole("checkbox")[1]);
      await userEvent.click(
        screen.getByRole("button", { name: /Create volume group/ })
      );

      rerender(<AvailableStorageTable canEditStorage node={machine} />, {
        state,
      });

      screen.getAllByRole("checkbox").forEach((checkbox) => {
        expect(checkbox).toBeDisabled();
      });
    });

    it("can trigger a create cache set form for a partition", async () => {
      const partition = factory.nodePartition({ filesystem: null });
      const machine = factory.machineDetails({
        disks: [
          factory.nodeDisk({
            available_size: 0,
            partitions: [partition],
          }),
        ],
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
      renderWithProviders(
        <AvailableStorageTable canEditStorage node={machine} />,
        { state }
      );

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: /Create cache set/ })
      );

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: CreateCacheSet,
        })
      );
    });

    it("can trigger a form to delete a volume group", async () => {
      const disk = factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        type: DiskTypes.VOLUME_GROUP,
        used_size: 0,
      });
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
      renderWithProviders(
        <AvailableStorageTable canEditStorage node={machine} />,
        { state }
      );

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: /Remove volume group/ })
      );

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: DeleteVolumeGroup,
        })
      );
    });

    it("can delete a partition", async () => {
      const partition = factory.nodePartition();
      const machine = factory.machineDetails({
        disks: [
          factory.nodeDisk({
            available_size: MIN_PARTITION_SIZE - 1,
            partitions: [partition],
            type: DiskTypes.PHYSICAL,
          }),
        ],
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
      renderWithProviders(
        <AvailableStorageTable canEditStorage node={machine} />,
        { state }
      );

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: /Remove partition/ })
      );

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: DeletePartition,
        })
      );
    });
  });
});
