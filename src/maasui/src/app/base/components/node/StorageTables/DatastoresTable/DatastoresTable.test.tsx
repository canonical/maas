import { describe } from "vitest";

import DatastoresTable from "./DatastoresTable";

import RemoveDatastore from "@/app/base/components/node/StorageTables/DatastoresTable/RemoveDatastore";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import type { Disk, Filesystem } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  mockIsPending,
  renderWithProviders,
  waitFor,
  mockSidePanel,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("DatastoresTable", () => {
  let state: RootState;
  let machine: MachineDetails;
  let controller: ControllerDetails;
  let datastore: Filesystem;
  let notDatastore: Filesystem;
  let dsDisk: Disk;
  let notDsDisk: Disk;

  beforeEach(() => {
    [datastore, notDatastore] = [
      factory.nodeFilesystem({ fstype: "vmfs6" }),
      factory.nodeFilesystem({ fstype: "fat32" }),
    ];
    [dsDisk, notDsDisk] = [
      factory.nodeDisk({ name: "datastore", filesystem: datastore }),
      factory.nodeDisk({ name: "not-datastore", filesystem: notDatastore }),
    ];
    controller = factory.controllerDetails({
      disks: [
        factory.nodeDisk({
          name: "datastore",
          filesystem: factory.nodeFilesystem({ fstype: "vmfs6" }),
        }),
      ],
      system_id: "abc123",
    });
    machine = factory.machineDetails({
      disks: [dsDisk, notDsDisk],
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
    // TODO: enable test once datastores are fetched through v3
    it.skip("displays a loading component if datastores are loading", async () => {
      mockIsPending();
      renderWithProviders(<DatastoresTable canEditStorage node={machine} />, {
        state,
      });

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      const notDatastore = factory.nodeFilesystem({ fstype: "fat32" });
      const machine = factory.machineDetails({
        disks: [
          factory.nodeDisk({ name: "not-datastore", filesystem: notDatastore }),
        ],
        system_id: "abc123",
      });
      state.machine.items = [machine];
      renderWithProviders(<DatastoresTable canEditStorage node={machine} />, {
        state,
      });

      await waitFor(() => {
        expect(screen.getByText("No datastores detected.")).toBeInTheDocument();
      });
    });

    describe("displays the columns correctly", () => {
      it("shows an action column if node is a machine", () => {
        renderWithProviders(<DatastoresTable canEditStorage node={machine} />, {
          state,
        });

        ["Name", "Size", "Filesystem", "Mount point", "Actions"].forEach(
          (column) => {
            expect(
              screen.getByRole("columnheader", {
                name: new RegExp(`^${column}`, "i"),
              })
            ).toBeInTheDocument();
          }
        );
      });

      it("does not show action column if node is a controller", () => {
        renderWithProviders(
          <DatastoresTable canEditStorage node={controller} />,
          { state }
        );

        ["Name", "Size", "Filesystem", "Mount point"].forEach((column) => {
          expect(
            screen.getByRole("columnheader", {
              name: new RegExp(`^${column}`, "i"),
            })
          ).toBeInTheDocument();
        });

        expect(
          screen.queryByRole("columnheader", { name: "Actions" })
        ).not.toBeInTheDocument();
      });
    });

    it("only shows filesystems that are VMFS6 datastores", () => {
      renderWithProviders(<DatastoresTable canEditStorage node={machine} />, {
        state,
      });

      expect(screen.getByRole("cell", { name: dsDisk.name })).toHaveClass(
        "name"
      );
      expect(
        screen.queryByRole("cell", { name: notDsDisk.name })
      ).not.toBeInTheDocument();
    });
  });

  describe("actions", () => {
    it("can remove a datastore if node is a machine", async () => {
      renderWithProviders(<DatastoresTable canEditStorage node={machine} />, {
        state,
      });

      await userEvent.click(
        screen.getByRole("button", { name: /Take action/ })
      );
      await userEvent.click(
        screen.getByRole("button", { name: "Remove datastore..." })
      );

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: RemoveDatastore,
          props: {
            diskId: dsDisk.id,
            systemId: machine.system_id,
          },
        })
      );
    });
  });
});
