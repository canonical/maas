import { isTransientStatus } from "./status";

import { NodeStatusCode } from "@/app/store/types/node";

describe("machine status utils", () => {
  describe("isTransientStatus", () => {
    it("returns whether a status is a transient status", () => {
      expect(isTransientStatus(NodeStatusCode.ALLOCATED)).toBe(false);
      expect(isTransientStatus(NodeStatusCode.BROKEN)).toBe(false);
      expect(isTransientStatus(NodeStatusCode.COMMISSIONING)).toBe(true);
      expect(isTransientStatus(NodeStatusCode.DEPLOYED)).toBe(false);
      expect(isTransientStatus(NodeStatusCode.DEPLOYING)).toBe(true);
      expect(isTransientStatus(NodeStatusCode.DISK_ERASING)).toBe(true);
      expect(isTransientStatus(NodeStatusCode.ENTERING_RESCUE_MODE)).toBe(true);
      expect(isTransientStatus(NodeStatusCode.EXITING_RESCUE_MODE)).toBe(true);
      expect(isTransientStatus(NodeStatusCode.FAILED_COMMISSIONING)).toBe(
        false
      );
      expect(isTransientStatus(NodeStatusCode.FAILED_DEPLOYMENT)).toBe(false);
      expect(isTransientStatus(NodeStatusCode.FAILED_DISK_ERASING)).toBe(false);
      expect(
        isTransientStatus(NodeStatusCode.FAILED_ENTERING_RESCUE_MODE)
      ).toBe(false);
      expect(isTransientStatus(NodeStatusCode.FAILED_EXITING_RESCUE_MODE)).toBe(
        false
      );
      expect(isTransientStatus(NodeStatusCode.FAILED_RELEASING)).toBe(false);
      expect(isTransientStatus(NodeStatusCode.FAILED_TESTING)).toBe(false);
      expect(isTransientStatus(NodeStatusCode.MISSING)).toBe(false);
      expect(isTransientStatus(NodeStatusCode.NEW)).toBe(false);
      expect(isTransientStatus(NodeStatusCode.READY)).toBe(false);
      expect(isTransientStatus(NodeStatusCode.RELEASING)).toBe(true);
      expect(isTransientStatus(NodeStatusCode.RESCUE_MODE)).toBe(false);
      expect(isTransientStatus(NodeStatusCode.RESERVED)).toBe(false);
      expect(isTransientStatus(NodeStatusCode.RETIRED)).toBe(false);
      expect(isTransientStatus(NodeStatusCode.TESTING)).toBe(true);
    });
  });
});
