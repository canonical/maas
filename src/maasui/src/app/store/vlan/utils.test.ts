import {
  getDHCPStatus,
  getFullVLANName,
  getVLANDisplay,
  isVLANDetails,
} from "./utils";

import { VlanVid } from "@/app/store/vlan/types";
import * as factory from "@/testing/factories";

describe("vlan utils", () => {
  describe("getVLANDisplay", () => {
    it("returns nothing if vlan undefined", () => {
      expect(getVLANDisplay(null)).toBe(null);
    });

    it("returns just vid", () => {
      const vlan = factory.vlan({ vid: 5, name: "" });
      expect(getVLANDisplay(vlan)).toBe("5");
    });

    it("can display as untagged", () => {
      const vlan = factory.vlan({ vid: VlanVid.UNTAGGED });
      expect(getVLANDisplay(vlan)).toBe("untagged");
    });

    it("returns vid + name", () => {
      const vlan = factory.vlan({ vid: 5, name: "vlan-name" });
      expect(getVLANDisplay(vlan)).toBe("5 (vlan-name)");
    });
  });

  describe("getFullVLANName", () => {
    it("generates a full name for a vlan", () => {
      const fabrics = [factory.fabric({ id: 99, name: "fabric-name" })];
      const vlan = factory.vlan({ fabric: 99, name: "vlan-name", vid: 101 });
      expect(getFullVLANName(vlan.id, [vlan], fabrics)).toBe(
        "fabric-name.101 (vlan-name)"
      );
    });

    it("handles a vlan that is not found", () => {
      const fabrics = [factory.fabric({ id: 99, name: "fabric-name" })];
      const vlan = factory.vlan({
        id: 10,
        fabric: 99,
        name: "vlan-name",
        vid: 101,
      });
      expect(getFullVLANName(11, [vlan], fabrics)).toBe(null);
    });

    it("handles a fabric that is not found", () => {
      const fabrics = [factory.fabric({ id: 100, name: "fabric-name" })];
      const vlan = factory.vlan({ fabric: 99, name: "vlan-name", vid: 101 });
      expect(getFullVLANName(vlan.id, [vlan], fabrics)).toBe(null);
    });
  });

  describe("getDHCPStatus", () => {
    it("returns correct text if dhcp is provided by MAAS", () => {
      const vlan = factory.vlan({ external_dhcp: null, dhcp_on: true });
      expect(getDHCPStatus(vlan, [], [])).toEqual("MAAS-provided");
    });

    it("returns correct text if dhcp is provided externally", () => {
      const vlan = factory.vlan({ external_dhcp: "127.0.0.1", dhcp_on: true });
      expect(getDHCPStatus(vlan, [], [])).toEqual("External (127.0.0.1)");
    });

    it("returns correct text if dhcp is disabled", () => {
      const vlan = factory.vlan({ external_dhcp: null, dhcp_on: false });
      expect(getDHCPStatus(vlan, [], [])).toEqual("No DHCP");
    });

    it("returns correct text if vlan is null", () => {
      expect(getDHCPStatus(null, [], [])).toEqual("No DHCP");
    });

    it("returns correct text if DHCP is relayed", () => {
      const vlan = factory.vlan({ fabric: 1, relay_vlan: 5001 });
      expect(getDHCPStatus(vlan, [], [])).toEqual("Relayed");
    });

    it("returns correct text if DHCP is relayed and full name required", () => {
      const fabrics = [factory.fabric({ id: 1, name: "fabric-1" })];
      const vlans = [
        factory.vlan({ id: 2, relay_vlan: 3, vid: 99 }),
        factory.vlan({ fabric: 1, id: 3, vid: 101, name: "test-vlan" }),
      ];
      expect(getDHCPStatus(vlans[0], vlans, fabrics, true)).toEqual(
        "Relayed via fabric-1.101 (test-vlan)"
      );
    });
  });

  describe("isVLANDetails", () => {
    it("handles the null case", () => {
      expect(isVLANDetails()).toBe(false);
      expect(isVLANDetails(null)).toBe(false);
    });

    it("correctly returns whether a subnet is the detailed type", () => {
      const vlan = factory.vlan();
      const vlanDetails = factory.vlanDetails();
      expect(isVLANDetails(vlan)).toBe(false);
      expect(isVLANDetails(vlanDetails)).toBe(true);
    });
  });
});
