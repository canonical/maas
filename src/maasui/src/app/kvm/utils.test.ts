import { getSortedPoolsArray, memoryWithUnit } from "./utils";

import * as factory from "@/testing/factories";

describe("kvm utils", () => {
  describe("memoryWithUnit", () => {
    it("correctly formats memory in bytes to a readable string", () => {
      expect(memoryWithUnit(0)).toBe("0B");
      expect(memoryWithUnit(1)).toBe("1B");
      expect(memoryWithUnit(1024)).toBe("1KiB");
      expect(memoryWithUnit(5000000000)).toBe("4.66GiB");
    });
  });

  describe("getSortedPoolsArray", () => {
    it("correctly returns a sorted array of pools in a pod", () => {
      const poolA = factory.podStoragePoolResource({ id: "a" });
      const poolB = factory.podStoragePoolResource({ id: "b" });
      const poolC = factory.podStoragePoolResource({ id: "c" });
      const pools = {
        poolC,
        poolB,
        poolA,
      };
      const defaultPoolId = "b";
      expect(getSortedPoolsArray(pools, defaultPoolId)).toStrictEqual([
        ["poolB", poolB],
        ["poolA", poolA],
        ["poolC", poolC],
      ]);
    });

    it("correctly returns a sorted array of pools in a cluster", () => {
      const poolA = factory.vmClusterStoragePoolResource();
      const poolB = factory.vmClusterStoragePoolResource();
      const poolC = factory.vmClusterStoragePoolResource();
      const pools = {
        poolC,
        poolA,
        poolB,
      };
      expect(getSortedPoolsArray(pools)).toStrictEqual([
        ["poolA", poolA],
        ["poolB", poolB],
        ["poolC", poolC],
      ]);
    });
  });
});
