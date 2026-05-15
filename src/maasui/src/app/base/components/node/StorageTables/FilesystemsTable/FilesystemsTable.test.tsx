import userEvent from "@testing-library/user-event";
import { describe } from "vitest";

import FilesystemsTable from "./FilesystemsTable";

import DeleteFilesystem from "@/app/base/components/node/StorageTables/FilesystemsTable/DeleteFilesystem";
import DeleteSpecialFilesystem from "@/app/base/components/node/StorageTables/FilesystemsTable/DeleteSpecialFilesystem";
import UnmountFilesystem from "@/app/base/components/node/StorageTables/FilesystemsTable/UnmountFilesystem";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import type { Disk, Filesystem, Partition } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  mockIsPending,
  mockSidePanel,
  renderWithProviders,
  screen,
  waitFor,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("FilesystemsTable", () => {
  let state: RootState;
  let machine: MachineDetails;
  let controller: ControllerDetails;
  let disk: Disk;
  let partition: Partition;
  let filesystem: Filesystem;

  beforeEach(() => {
    filesystem = factory.nodeFilesystem({ mount_point: "/disk-fs/path" });
    partition = factory.nodePartition({ filesystem });
    disk = factory.nodeDisk({
      filesystem: null,
      partitions: [partition],
    });
    controller = factory.controllerDetails({
      disks: [disk],
      system_id: "abc123",
    });
    machine = factory.machineDetails({
      disks: [
        factory.nodeDisk({
          filesystem: null,
          partitions: [factory.nodePartition({ filesystem: null })],
        }),
      ],
      system_id: "abc123",
    });
    state = factory.rootState({
      machine: factory.machineState({
        items: [machine],
      }),
      controller: factory.controllerState({
        items: [controller],
      }),
    });
  });

  describe("display", () => {
    // TODO: enable test once filesystems are fetched through v3
    it.skip("displays a loading component if filesystems are loading", async () => {
      mockIsPending();
      renderWithProviders(<FilesystemsTable canEditStorage node={machine} />, {
        state,
      });

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      renderWithProviders(<FilesystemsTable canEditStorage node={machine} />, {
        state,
      });

      await waitFor(() => {
        expect(screen.getByText("No filesystems defined.")).toBeInTheDocument();
      });
    });

    describe("displays the columns correctly", () => {
      it("shows an action column if node is a machine", () => {
        renderWithProviders(
          <FilesystemsTable canEditStorage node={machine} />,
          { state }
        );

        [
          "Name",
          "Size",
          "Filesystem",
          "Mount point",
          "Mount options",
          "Actions",
        ].forEach((column) => {
          expect(
            screen.getByRole("columnheader", {
              name: new RegExp(`^${column}`, "i"),
            })
          ).toBeInTheDocument();
        });
      });

      it("does not show action column if node is a controller", () => {
        renderWithProviders(
          <FilesystemsTable canEditStorage node={controller} />,
          { state }
        );

        ["Name", "Size", "Filesystem", "Mount point", "Mount options"].forEach(
          (column) => {
            expect(
              screen.getByRole("columnheader", {
                name: new RegExp(`^${column}`, "i"),
              })
            ).toBeInTheDocument();
          }
        );

        expect(
          screen.queryByRole("columnheader", { name: "Actions" })
        ).not.toBeInTheDocument();
      });
    });

    it("can show filesystems associated with disks", () => {
      const filesystem = factory.nodeFilesystem({
        mount_point: "/disk-fs/path",
      });
      const machine = factory.machineDetails({
        disks: [
          factory.nodeDisk({ filesystem, name: "disk-fs", partitions: [] }),
        ],
        system_id: "abc123",
      });
      state.machine.items = [machine];

      renderWithProviders(<FilesystemsTable canEditStorage node={machine} />, {
        state,
      });

      expect(screen.getByRole("cell", { name: "disk-fs" })).toHaveClass("name");
      expect(screen.getByRole("cell", { name: "/disk-fs/path" })).toHaveClass(
        "mountPoint"
      );
    });

    it("can show filesystems associated with partitions", () => {
      const filesystem = factory.nodeFilesystem({
        mount_point: "/partition-fs/path",
      });
      const machine = factory.machineDetails({
        disks: [
          factory.nodeDisk({
            filesystem: null,
            partitions: [
              factory.nodePartition({ filesystem, name: "partition-fs" }),
            ],
          }),
        ],
        system_id: "abc123",
      });
      state.machine.items = [machine];

      renderWithProviders(<FilesystemsTable canEditStorage node={machine} />, {
        state,
      });

      expect(screen.getByRole("cell", { name: "partition-fs" })).toHaveClass(
        "name"
      );
      expect(
        screen.getByRole("cell", { name: "/partition-fs/path" })
      ).toHaveClass("mountPoint");
    });

    it("can show special filesystems", () => {
      const specialFilesystem = factory.nodeFilesystem({
        mount_point: "/special-fs/path",
        fstype: "tmpfs",
      });
      const machine = factory.machineDetails({
        disks: [factory.nodeDisk()],
        special_filesystems: [specialFilesystem],
        system_id: "abc123",
      });
      state.machine.items = [machine];

      renderWithProviders(<FilesystemsTable canEditStorage node={machine} />, {
        state,
      });

      expect(screen.getAllByRole("cell", { name: "—" })[0]).toHaveClass("name");
      expect(
        screen.getByRole("cell", { name: "/special-fs/path" })
      ).toHaveClass("mountPoint");
    });
  });

  describe("actions", () => {
    it("disables the action menu if node is a machine and storage can't be edited", () => {
      const filesystem = factory.nodeFilesystem({
        mount_point: "/disk-fs/path",
      });
      const partition = factory.nodePartition({ filesystem });
      const disk = factory.nodeDisk({
        filesystem: null,
        partitions: [partition],
      });
      const machine = factory.machineDetails({
        disks: [disk],
        system_id: "abc123",
      });
      state.machine.items = [machine];
      state.machine.statuses = factory.machineStatuses({
        abc123: factory.machineStatus(),
      });

      renderWithProviders(
        <FilesystemsTable canEditStorage={false} node={machine} />,
        {
          state,
        }
      );

      expect(
        screen.getByRole("button", { name: /Take action/ })
      ).toBeAriaDisabled();
    });

    it("can remove a disk's filesystem if node is a machine", async () => {
      const filesystem = factory.nodeFilesystem({
        mount_point: "/disk-fs/path",
      });
      const disk = factory.nodeDisk({ filesystem, partitions: [] });
      const machine = factory.machineDetails({
        disks: [disk],
        system_id: "abc123",
      });
      state.machine.items = [machine];
      state.machine.statuses = factory.machineStatuses({
        abc123: factory.machineStatus(),
      });

      renderWithProviders(<FilesystemsTable canEditStorage node={machine} />, {
        state,
      });

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: "Remove filesystem..." })
      );
      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: DeleteFilesystem,
        })
      );
    });

    it("can remove a partition's filesystem if node is a machine", async () => {
      const filesystem = factory.nodeFilesystem({
        mount_point: "/disk-fs/path",
      });
      const partition = factory.nodePartition({ filesystem });
      const disk = factory.nodeDisk({
        filesystem: null,
        partitions: [partition],
      });
      const machine = factory.machineDetails({
        disks: [disk],
        system_id: "abc123",
      });
      state.machine.items = [machine];
      state.machine.statuses = factory.machineStatuses({
        abc123: factory.machineStatus(),
      });

      renderWithProviders(<FilesystemsTable canEditStorage node={machine} />, {
        state,
      });

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: "Remove filesystem..." })
      );
      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: DeleteFilesystem,
        })
      );
    });

    it("can remove a special filesystem if node is a machine", async () => {
      const filesystem = factory.nodeFilesystem({
        fstype: "tmpfs",
        mount_point: "/disk-fs/path",
      });
      const machine = factory.machineDetails({
        disks: [],
        special_filesystems: [filesystem],
        system_id: "abc123",
      });
      state.machine.items = [machine];
      state.machine.statuses = factory.machineStatuses({
        abc123: factory.machineStatus(),
      });

      renderWithProviders(<FilesystemsTable canEditStorage node={machine} />, {
        state,
      });

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: "Remove filesystem..." })
      );
      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: DeleteSpecialFilesystem,
        })
      );
    });

    it("can unmount a disk's filesystem if node is a machine", async () => {
      const filesystem = factory.nodeFilesystem({
        mount_point: "/disk-fs/path",
      });
      const disk = factory.nodeDisk({ filesystem, partitions: [] });
      const machine = factory.machineDetails({
        disks: [disk],
        system_id: "abc123",
      });
      state.machine.items = [machine];
      state.machine.statuses = factory.machineStatuses({
        abc123: factory.machineStatus(),
      });

      renderWithProviders(<FilesystemsTable canEditStorage node={machine} />, {
        state,
      });

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: "Unmount filesystem..." })
      );
      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: UnmountFilesystem,
        })
      );
    });

    it("can unmount a partition's filesystem if node is a machine", async () => {
      const filesystem = factory.nodeFilesystem({
        mount_point: "/disk-fs/path",
      });
      const partition = factory.nodePartition({ filesystem });
      const disk = factory.nodeDisk({
        filesystem: null,
        partitions: [partition],
      });
      const machine = factory.machineDetails({
        disks: [disk],
        system_id: "abc123",
      });
      state.machine.items = [machine];
      state.machine.statuses = factory.machineStatuses({
        abc123: factory.machineStatus(),
      });

      renderWithProviders(<FilesystemsTable canEditStorage node={machine} />, {
        state,
      });

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: "Unmount filesystem..." })
      );
      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: UnmountFilesystem,
        })
      );
    });
  });
});
