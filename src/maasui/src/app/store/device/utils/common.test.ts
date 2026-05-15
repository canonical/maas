import { isDeviceDetails, getIpAssignmentDisplay } from "./common";

import { DeviceIpAssignment } from "@/app/store/device/types";
import * as factory from "@/testing/factories";

describe("device utils", () => {
  describe("isDeviceDetails", () => {
    it("identifies device details", () => {
      const deviceDetails = factory.deviceDetails();
      expect(isDeviceDetails(deviceDetails)).toBe(true);
    });

    it("handles base device", () => {
      const baseDevice = factory.device();
      expect(isDeviceDetails(baseDevice)).toBe(false);
    });

    it("handles no device", () => {
      expect(isDeviceDetails()).toBe(false);
    });

    it("handles null", () => {
      expect(isDeviceDetails(null)).toBe(false);
    });
  });

  describe("getIpAssignmentDisplay", () => {
    it("handles dynamic IP assignment", () => {
      expect(getIpAssignmentDisplay(DeviceIpAssignment.DYNAMIC)).toBe(
        "Dynamic"
      );
    });

    it("handles external IP assignement", () => {
      expect(getIpAssignmentDisplay(DeviceIpAssignment.EXTERNAL)).toBe(
        "Static (Externally managed)"
      );
    });

    it("handles static IP assignment", () => {
      expect(getIpAssignmentDisplay(DeviceIpAssignment.STATIC)).toBe(
        "Static (Client configured)"
      );
    });

    it("handles unknown IP assignment", () => {
      expect(getIpAssignmentDisplay()).toBe("Unknown");
    });
  });
});
