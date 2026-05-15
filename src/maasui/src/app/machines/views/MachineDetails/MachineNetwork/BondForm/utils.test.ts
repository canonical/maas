import { LinkMonitoring, MacSource } from "./types";
import {
  getFirstSelected,
  getParentIds,
  getValidNics,
  prepareBondPayload,
} from "./utils";

import {
  BondLacpRate,
  BondMode,
  BondXmitHashPolicy,
} from "@/app/store/general/types";
import { NetworkInterfaceTypes, NetworkLinkMode } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";

describe("BondForm utils", () => {
  describe("getFirstSelected", () => {
    it("sorts the nics by name and gets the first interface", () => {
      const interfaces = [
        factory.machineInterface({
          name: "bbb",
        }),
        factory.machineInterface({
          name: "ccc",
        }),
        factory.machineInterface({
          name: "aaa",
        }),
      ];
      const machine = factory.machineDetails({
        interfaces,
      });
      expect(
        getFirstSelected(machine, [
          { nicId: interfaces[0].id },
          { nicId: interfaces[1].id },
          { nicId: interfaces[2].id },
        ])
      ).toStrictEqual({ nicId: interfaces[2].id });
    });
  });

  describe("getValidNics", () => {
    it("finds valid interfaces for a new bond", () => {
      const interfaces = [
        factory.machineInterface({
          type: NetworkInterfaceTypes.PHYSICAL,
          vlan_id: 1,
        }),
        // Invalid because it has a different VLAN.
        factory.machineInterface({
          type: NetworkInterfaceTypes.PHYSICAL,
          vlan_id: 2,
        }),
        factory.machineInterface({
          type: NetworkInterfaceTypes.PHYSICAL,
          vlan_id: 1,
        }),
        // Invalid because it is not physical.
        factory.machineInterface({
          type: NetworkInterfaceTypes.VLAN,
          vlan_id: 1,
        }),
        // Invalid because it is already in a bond
        factory.machineInterface({
          id: 2200,
          children: [900],
          type: NetworkInterfaceTypes.PHYSICAL,
          vlan_id: 1,
        }),
        // Invalid because it is a bond
        factory.machineInterface({
          parents: [2200],
          id: 900,
          type: NetworkInterfaceTypes.BOND,
          vlan_id: 1,
        }),
      ];
      const machine = factory.machineDetails({
        interfaces,
      });
      expect(getValidNics(machine, 1)).toStrictEqual([
        interfaces[0],
        interfaces[2],
      ]);
    });

    it("finds valid interfaces for an existing bond", () => {
      const interfaces = [
        // This is the bond
        factory.machineInterface({
          children: [900],
          id: 800,
          type: NetworkInterfaceTypes.BOND,
          vlan_id: 1,
        }),
        // Valid because it is not in a bond.
        factory.machineInterface({
          type: NetworkInterfaceTypes.PHYSICAL,
          vlan_id: 1,
        }),
        // Valid because it is in the bond.
        factory.machineInterface({
          id: 900,
          parents: [800],
          type: NetworkInterfaceTypes.PHYSICAL,
          vlan_id: 1,
        }),
        // Invalid because it is in a different bond.
        factory.machineInterface({
          children: [2300],
          id: 2200,
          type: NetworkInterfaceTypes.PHYSICAL,
          vlan_id: 1,
        }),
        // Invalid because it is a different bond.
        factory.machineInterface({
          id: 2300,
          parents: [2200],
          type: NetworkInterfaceTypes.BOND,
          vlan_id: 1,
        }),
      ];
      const machine = factory.machineDetails({
        interfaces,
      });
      expect(getValidNics(machine, 1, interfaces[0])).toStrictEqual([
        interfaces[1],
        interfaces[2],
      ]);
    });
  });

  describe("getParentIds", () => {
    it("gets all the parent ids from the selected state", () => {
      expect(
        getParentIds([{ nicId: 1 }, { linkId: 2 }, { nicId: 3 }])
      ).toStrictEqual([1, 3]);
    });
  });

  describe("prepareBondPayload", () => {
    it("cleans and prepares the payload with a nic and link", () => {
      const nic = factory.machineInterface();
      const link = factory.networkLink();
      const values = {
        // Should be removed.
        linkMonitoring: LinkMonitoring.MII,
        mac_address: "",
        macNic: "aa:bb:cc:dd:ee:ff",
        macSource: MacSource.NIC,
        // Should not be removed,
        bond_downdelay: 0,
        bond_lacp_rate: BondLacpRate.FAST,
        bond_mode: BondMode.ACTIVE_BACKUP,
        bond_miimon: 20,
        bond_updelay: 30,
        bond_xmit_hash_policy: BondXmitHashPolicy.ENCAP2_3,
        fabric: 1,
        ip_address: "1.2.3.4",
        mode: NetworkLinkMode.LINK_UP,
        name: "bond2",
        subnet: 1,
        tags: ["a", "tag"],
        vlan: 1,
      };
      expect(
        prepareBondPayload(
          values,
          [{ nicId: 1 }, { nicId: 2 }],
          "abc123",
          nic,
          link
        )
      ).toStrictEqual({
        bond_downdelay: 0,
        bond_lacp_rate: BondLacpRate.FAST,
        bond_mode: BondMode.ACTIVE_BACKUP,
        bond_miimon: 20,
        bond_updelay: 30,
        bond_xmit_hash_policy: BondXmitHashPolicy.ENCAP2_3,
        fabric: 1,
        ip_address: "1.2.3.4",
        mode: NetworkLinkMode.LINK_UP,
        name: "bond2",
        subnet: 1,
        tags: ["a", "tag"],
        vlan: 1,
        // The following fields should be appended.
        interface_id: nic.id,
        link_id: link.id,
        parents: [1, 2],
        system_id: "abc123",
      });
    });

    it("can ignore the nic and link if not provided", () => {
      const values = {
        linkMonitoring: LinkMonitoring.MII,
        mac_address: "",
        bond_downdelay: 0,
        bond_lacp_rate: BondLacpRate.FAST,
        bond_mode: BondMode.ACTIVE_BACKUP,
        bond_miimon: 20,
        bond_updelay: 30,
        bond_xmit_hash_policy: BondXmitHashPolicy.ENCAP2_3,
        fabric: 1,
        ip_address: "1.2.3.4",
        macNic: "aa:bb:cc:dd:ee:ff",
        macSource: MacSource.NIC,
        mode: NetworkLinkMode.LINK_UP,
        name: "bond2",
        subnet: 1,
        tags: ["a", "tag"],
        vlan: 1,
      };
      const payload = prepareBondPayload(values, [], "abc123");
      expect(payload.link_id).toBeUndefined();
      expect(payload.interface_id).toBeUndefined();
    });
  });
});
