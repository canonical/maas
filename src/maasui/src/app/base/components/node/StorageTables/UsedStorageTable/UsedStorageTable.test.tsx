import { describe } from "vitest";

import UsedStorageTable from "./UsedStorageTable";

import urls from "@/app/base/urls";
import type { ControllerDetails } from "@/app/store/controller/types";
import { FilterControllers } from "@/app/store/controller/utils";
import { MIN_PARTITION_SIZE } from "@/app/store/machine/constants";
import type { MachineDetails } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { DiskTypes } from "@/app/store/types/enum";
import type { Disk } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  mockIsPending,
  renderWithProviders,
  screen,
  waitFor,
} from "@/testing/utils";

describe("UsedStorageTable", () => {
  let state: RootState;
  let machine: MachineDetails;
  let controller: ControllerDetails;
  let availableDisk: Disk;
  let usedDisk: Disk;

  beforeEach(() => {
    [availableDisk, usedDisk] = [
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        name: "available-disk",
        filesystem: null,
        type: DiskTypes.PHYSICAL,
        tags: ["abc"],
      }),
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE - 1,
        filesystem: null,
        name: "used-disk",
        type: DiskTypes.PHYSICAL,
        tags: ["abc"],
      }),
    ];
    machine = factory.machineDetails({
      disks: [availableDisk, usedDisk],
      system_id: "abc123",
    });
    controller = factory.controllerDetails({
      disks: [availableDisk, usedDisk],
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
    // TODO: enable test once used storages are fetched through v3
    it.skip("displays a loading component if storages are loading", async () => {
      mockIsPending();
      renderWithProviders(<UsedStorageTable node={machine} />, {
        state,
      });

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      const noDiskMachine = factory.machineDetails({
        disks: [],
        system_id: "abc123",
      });
      state.machine.items = [noDiskMachine];
      renderWithProviders(<UsedStorageTable node={noDiskMachine} />, {
        state,
      });

      await waitFor(() => {
        expect(
          screen.getByText("No disk or partition has been fully utilised.")
        ).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<UsedStorageTable node={machine} />, {
        state,
      });

      ["Name", "Model", "Boot", "Size", "Type", "Health", "Used for"].forEach(
        (column) => {
          expect(
            screen.getByRole("columnheader", {
              name: new RegExp(`^${column}`, "i"),
            })
          ).toBeInTheDocument();
        }
      );
    });

    it("only shows disks that are being used", () => {
      renderWithProviders(<UsedStorageTable node={machine} />, { state });

      expect(screen.getByText(usedDisk.name)).toBeInTheDocument();
      expect(screen.queryByText(availableDisk.name)).not.toBeInTheDocument();
    });

    it("can render storage tag links for a machine", () => {
      const filter = FilterMachines.filtersToQueryString({
        storage_tags: ["=abc"],
      });
      const href = `${urls.machines.index}${filter}`;

      renderWithProviders(<UsedStorageTable node={machine} />, { state });

      expect(screen.getByRole("link", { name: "abc" })).toHaveAttribute(
        "href",
        href
      );
    });

    it("can render storage tag links for a controller", () => {
      const filter = FilterControllers.filtersToQueryString({
        storage_tags: ["=abc"],
      });
      const href = `${urls.controllers.index}${filter}`;

      renderWithProviders(<UsedStorageTable node={controller} />, { state });

      expect(screen.getByRole("link", { name: "abc" })).toHaveAttribute(
        "href",
        href
      );
    });
  });
});
