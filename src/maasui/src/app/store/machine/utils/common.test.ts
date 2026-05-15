import {
  getHasSyncFailed,
  getMachineFieldScopes,
  getTagCountsForMachines,
  isMachineDetails,
  isDeployedWithHardwareSync,
  mapSortDirection,
  selectedToFilters,
  isUnconfiguredPowerType,
  getNodeStatusKey,
} from "./common";

import { SortDirection } from "@/app/base/types";
import { PowerFieldScope } from "@/app/store/general/types";
import { FetchSortDirection, FetchGroupKey } from "@/app/store/machine/types";
import { PowerState } from "@/app/store/types/enum";
import { NodeStatus, NodeStatusCode } from "@/app/store/types/node";
import * as factory from "@/testing/factories";

describe("common machine utils", () => {
  describe("isMachineDetails", () => {
    it("identifies machine details", () => {
      expect(isMachineDetails(factory.machineDetails())).toBe(true);
    });

    it("handles a machine", () => {
      expect(isMachineDetails(factory.machine())).toBe(false);
    });

    it("handles no machine", () => {
      expect(isMachineDetails()).toBe(false);
    });

    it("handles null", () => {
      expect(isMachineDetails(null)).toBe(false);
    });
  });

  describe("getTagCountsForMachines", () => {
    it("gets the tag ids and counts", () => {
      const machines = [
        factory.machine({ tags: [1, 2, 3] }),
        factory.machine({ tags: [3, 1, 4] }),
      ];
      expect(getTagCountsForMachines(machines)).toStrictEqual(
        new Map([
          [1, 2],
          [2, 1],
          [3, 2],
          [4, 1],
        ])
      );
    });
  });

  describe("getMachineFieldScopes", () => {
    it("gets the field scopes for a machine in a pod", () => {
      const machine = factory.machine({ pod: factory.modelRef() });

      expect(getMachineFieldScopes(machine)).toStrictEqual([
        PowerFieldScope.NODE,
      ]);
    });

    it("gets the field scopes for a machine not in a pod", () => {
      const machine = factory.machine({ pod: undefined });

      expect(getMachineFieldScopes(machine)).toStrictEqual([
        PowerFieldScope.BMC,
        PowerFieldScope.NODE,
      ]);
    });
  });

  describe("getHasSyncFailed", () => {
    it("returns false if is_sync_healthy is true or undefined", () => {
      expect(
        getHasSyncFailed(factory.machineDetails({ is_sync_healthy: true }))
      ).toBe(false);
      expect(
        getHasSyncFailed(factory.machineDetails({ is_sync_healthy: undefined }))
      ).toBe(false);
    });
    it("returns true if is_sync_healthy is false", () => {
      expect(
        getHasSyncFailed(factory.machineDetails({ is_sync_healthy: false }))
      ).toBe(true);
    });
  });

  describe("isDeployedWithHardwareSync", () => {
    it("returns false for deploying machines", () => {
      expect(
        isDeployedWithHardwareSync(
          factory.machineDetails({
            status: NodeStatus.DEPLOYING,
            enable_hw_sync: true,
          })
        )
      ).toBe(false);
    });

    it("returns true for deployed machines with hardware sync enabled", () => {
      expect(
        isDeployedWithHardwareSync(
          factory.machineDetails({
            status: NodeStatus.DEPLOYED,
            enable_hw_sync: true,
          })
        )
      ).toBe(true);
    });

    it("returns false for deployed machines with hardware sync disabled", () => {
      expect(
        isDeployedWithHardwareSync(
          factory.machineDetails({
            status: NodeStatus.DEPLOYED,
            enable_hw_sync: false,
          })
        )
      ).toBe(false);
    });
  });

  describe("mapSortDirection", () => {
    it("maps ascending", () => {
      expect(mapSortDirection(SortDirection.ASCENDING)).toBe(
        FetchSortDirection.Ascending
      );
    });

    it("maps descending", () => {
      expect(mapSortDirection(SortDirection.DESCENDING)).toBe(
        FetchSortDirection.Descending
      );
    });

    it("maps none", () => {
      expect(mapSortDirection(SortDirection.NONE)).toBeNull();
    });

    it("maps nullish values", () => {
      expect(mapSortDirection(undefined)).toBeNull();
      expect(mapSortDirection(null)).toBeNull();
    });
  });

  describe("selectedToFilters", () => {
    it("converts filter", () => {
      expect(
        selectedToFilters({ filter: { free_text: "some filter" } })
      ).toStrictEqual({ free_text: "some filter" });
    });

    it("converts items", () => {
      expect(selectedToFilters({ items: ["abc123", "def456"] })).toStrictEqual({
        id: ["abc123", "def456"],
      });
    });

    it("converts groups", () => {
      expect(
        selectedToFilters({
          groups: ["admin", "admin3"],
          grouping: FetchGroupKey.Owner,
        })
      ).toStrictEqual({ owner: ["=admin", "=admin3"] });
    });

    it("handles no filters", () => {
      expect(selectedToFilters({ items: [], groups: [] })).toBeNull();
    });
  });

  describe("isUnconfiguredPowerType", () => {
    it("returns true for unknown power state and new status code", () => {
      const machine = factory.machine({
        power_state: PowerState.UNKNOWN,
        status_code: NodeStatusCode.NEW,
      });

      expect(isUnconfiguredPowerType(machine)).toBe(true);
    });

    it("returns false if either power state or status criteria are not met", () => {
      const machine1 = factory.machine({
        power_state: PowerState.UNKNOWN,
        status_code: NodeStatusCode.READY,
      });
      const machine2 = factory.machine({
        power_state: PowerState.OFF,
        status_code: NodeStatusCode.NEW,
      });
      expect(isUnconfiguredPowerType(machine1)).toBe(false);
      expect(isUnconfiguredPowerType(machine2)).toBe(false);
    });
  });

  describe("getNodeStatusKey", () => {
    it("should return a key if value matches", () => {
      expect(getNodeStatusKey("Failed to enter rescue mode")).toBe(
        "FAILED_ENTERING_RESCUE_MODE"
      );
    });

    it("should return undefined if no key matches", () => {
      expect(getNodeStatusKey("NonExistentStatus")).toBeUndefined();
    });
  });
});
