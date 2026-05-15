import {
  canAddAlias,
  getBondOrBridgeChild,
  getBondOrBridgeParents,
  getInterfaceById,
  getInterfaceDiscovered,
  getInterfaceFabric,
  getInterfaceIPAddress,
  getInterfaceIPAddressOrMode,
  getInterfaceName,
  getInterfaceNumaNodes,
  getInterfaceSubnet,
  getInterfaceType,
  getInterfaceTypeText,
  getLinkFromNic,
  getLinkInterface,
  getLinkInterfaceById,
  getLinkMode,
  getLinkModeDisplay,
  getNextNicName,
  getRemoveTypeText,
  hasInterfaceType,
  isAlias,
  isBondOrBridgeChild,
  isBondOrBridgeParent,
  isBootInterface,
  isInterfaceConnected,
} from "./networking";

import {
  BridgeType,
  NetworkInterfaceTypes,
  NetworkLinkMode,
} from "@/app/store/types/enum";
import * as factory from "@/testing/factories";

describe("machine networking utils", () => {
  describe("getLinkInterface", () => {
    it("can get the interface a link belongs to", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [link, factory.networkLink()],
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getLinkInterface(machine, link)).toStrictEqual([nic, 0]);
    });

    it("does not get an interface if a link is not provided", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [link, factory.networkLink()],
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getLinkInterface(machine, null)).toStrictEqual([null, null]);
    });
  });

  describe("getLinkInterfaceById", () => {
    it("can get the interface a link belongs to", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [link, factory.networkLink()],
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getLinkInterfaceById(machine, link.id)).toStrictEqual([nic, 0]);
    });

    it("does not get an interface if a link is not provided", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [link, factory.networkLink()],
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getLinkInterfaceById(machine, null)).toStrictEqual([null, null]);
    });
  });

  describe("isAlias", () => {
    it("is not an alias if a link is not provided", () => {
      const nic = factory.machineInterface();
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(isAlias(machine, null)).toBe(false);
    });

    it("is not an alias if it is the first link item", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [link, factory.networkLink()],
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(isAlias(machine, link)).toBe(false);
    });

    it("is an alias if it is not the first link item", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [factory.networkLink(), link],
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(isAlias(machine, link)).toBe(true);
    });
  });

  describe("getInterfaceName", () => {
    it("gets the name of an interface", () => {
      const nic = factory.machineInterface({
        name: "br0",
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceName(machine, nic)).toBe("br0");
    });

    it("gets the name of an interface when providing a link", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [factory.networkLink(), link],
        name: "br0",
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceName(machine, null, link)).toBe("br0:1");
    });
  });

  describe("getInterfaceType", () => {
    it("gets the type of an interface", () => {
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.VLAN,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceType(machine, nic)).toBe(NetworkInterfaceTypes.VLAN);
    });

    it("gets the type of an interface when providing a link", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [factory.networkLink(), link],
        type: NetworkInterfaceTypes.VLAN,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceType(machine, null, link)).toBe(
        NetworkInterfaceTypes.ALIAS
      );
    });
  });

  describe("hasInterfaceType", () => {
    it("can check for a single type", () => {
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.VLAN,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(hasInterfaceType(NetworkInterfaceTypes.VLAN, machine, nic)).toBe(
        true
      );
    });

    it("can check for one of many types", () => {
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.VLAN,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(
        hasInterfaceType(
          [NetworkInterfaceTypes.BOND, NetworkInterfaceTypes.VLAN],
          machine,
          nic
        )
      ).toBe(true);
    });

    it("can check for the type of a link", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [factory.networkLink(), link],
        type: NetworkInterfaceTypes.VLAN,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(
        hasInterfaceType(NetworkInterfaceTypes.ALIAS, machine, null, link)
      ).toBe(true);
    });
  });

  describe("getLinkMode", () => {
    it("gets the mode of a link", () => {
      const link = factory.networkLink({ mode: NetworkLinkMode.AUTO });
      expect(getLinkMode(link)).toBe(NetworkLinkMode.AUTO);
    });

    it("is link_up when there are no links", () => {
      expect(getLinkMode(null)).toBe(NetworkLinkMode.LINK_UP);
    });
  });

  describe("getBondOrBridgeParents", () => {
    it("gets parents for a bond", () => {
      const interfaces = [
        factory.machineInterface(),
        factory.machineInterface(),
        factory.machineInterface(),
      ];
      const nic = factory.machineInterface({
        parents: [interfaces[0].id, interfaces[2].id],
        type: NetworkInterfaceTypes.BOND,
      });
      interfaces.push(nic);
      const machine = factory.machineDetails({ interfaces });
      expect(getBondOrBridgeParents(machine, nic)).toStrictEqual([
        interfaces[0],
        interfaces[2],
      ]);
    });

    it("gets parents for a bridge", () => {
      const interfaces = [
        factory.machineInterface(),
        factory.machineInterface(),
        factory.machineInterface(),
      ];
      const nic = factory.machineInterface({
        parents: [interfaces[0].id, interfaces[2].id],
        type: NetworkInterfaceTypes.BRIDGE,
      });
      interfaces.push(nic);
      const machine = factory.machineDetails({ interfaces });
      expect(getBondOrBridgeParents(machine, nic)).toStrictEqual([
        interfaces[0],
        interfaces[2],
      ]);
    });

    it("does not get parents for links", () => {
      const interfaces = [
        factory.machineInterface(),
        factory.machineInterface(),
        factory.machineInterface(),
      ];
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [link],
        parents: [interfaces[0].id, interfaces[2].id],
        type: NetworkInterfaceTypes.VLAN,
      });
      interfaces.push(nic);
      const machine = factory.machineDetails({ interfaces });
      expect(getBondOrBridgeParents(machine, null, link)).toStrictEqual([]);
    });

    it("does not get parents for other types", () => {
      const interfaces = [
        factory.machineInterface(),
        factory.machineInterface(),
        factory.machineInterface(),
      ];
      const nic = factory.machineInterface({
        parents: [interfaces[0].id, interfaces[2].id],
        type: NetworkInterfaceTypes.VLAN,
      });
      interfaces.push(nic);
      const machine = factory.machineDetails({ interfaces });
      expect(getBondOrBridgeParents(machine, nic)).toStrictEqual([]);
    });
  });

  describe("getBondOrBridgeChild", () => {
    it("gets the child interface for a parent", () => {
      const nic = factory.machineInterface({
        parents: [99],
        type: NetworkInterfaceTypes.BOND,
      });
      const parent = factory.machineInterface({
        children: [nic.id],
        id: 99,
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic, parent] });
      expect(getBondOrBridgeChild(machine, parent)).toStrictEqual(nic);
    });

    it("gets the child interface for a parent with multiple children", () => {
      const nic = factory.machineInterface({
        parents: [99],
        type: NetworkInterfaceTypes.BOND,
      });
      const vlan = factory.machineInterface({
        parents: [99],
        type: NetworkInterfaceTypes.VLAN,
      });
      const parent = factory.machineInterface({
        children: [vlan.id, nic.id],
        id: 99,
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({
        interfaces: [nic, parent, vlan],
      });
      expect(getBondOrBridgeChild(machine, parent)).toStrictEqual(nic);
    });

    it("gets the child interface via an alias", () => {
      const nic = factory.machineInterface({
        parents: [99],
        type: NetworkInterfaceTypes.BOND,
      });
      const link = factory.networkLink();
      const parent = factory.machineInterface({
        links: [link],
        children: [nic.id],
        id: 99,
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic, parent] });
      expect(getBondOrBridgeChild(machine, null, link)).toStrictEqual(nic);
    });
  });

  describe("isBondOrBridgeParent", () => {
    it("can be an interface parent", () => {
      const nic = factory.machineInterface({
        parents: [99],
        type: NetworkInterfaceTypes.BOND,
      });
      const parent = factory.machineInterface({
        children: [nic.id],
        id: 99,
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic, parent] });
      expect(isBondOrBridgeParent(machine, parent)).toBe(true);
    });

    it("is not an interface parent when the child interface is not a bond or bridge", () => {
      const nic = factory.machineInterface({
        parents: [99],
        type: NetworkInterfaceTypes.ALIAS,
      });
      const vlan = factory.machineInterface({
        parents: [99],
        type: NetworkInterfaceTypes.VLAN,
      });
      const parent = factory.machineInterface({
        children: [nic.id, vlan.id],
        id: 99,
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({
        interfaces: [nic, parent, vlan],
      });
      expect(isBondOrBridgeParent(machine, parent)).toBe(false);
    });

    it("is not an interface parent providing an alias", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [link],
        parents: [99],
        type: NetworkInterfaceTypes.ALIAS,
      });
      const parent = factory.machineInterface({
        children: [nic.id, 101],
        id: 99,
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic, parent] });
      expect(isBondOrBridgeParent(machine, null, link)).toBe(false);
    });
  });

  describe("isBondOrBridgeChild", () => {
    it("can be an interface child", () => {
      const nic = factory.machineInterface({
        parents: [99],
        type: NetworkInterfaceTypes.BOND,
      });
      const parent = factory.machineInterface({
        children: [nic.id],
        id: 99,
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic, parent] });
      expect(isBondOrBridgeChild(machine, nic)).toBe(true);
    });

    it("is not an interface child when there are no parents", () => {
      const nic = factory.machineInterface({
        parents: [],
        type: NetworkInterfaceTypes.BOND,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(isBondOrBridgeChild(machine, nic)).toBe(false);
    });

    it("is not an interface child if it is not a bond or bridge", () => {
      const nic = factory.machineInterface({
        parents: [99],
        type: NetworkInterfaceTypes.ALIAS,
      });
      const parent = factory.machineInterface({
        children: [nic.id, 101],
        id: 99,
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic, parent] });
      expect(isBondOrBridgeChild(machine, nic)).toBe(false);
    });

    it("is not an interface child when providing an alias", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [link],
        parents: [99],
        type: NetworkInterfaceTypes.ALIAS,
      });
      const parent = factory.machineInterface({
        children: [nic.id, 101],
        id: 99,
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic, parent] });
      expect(isBondOrBridgeChild(machine, null, link)).toBe(false);
    });
  });

  describe("getInterfaceNumaNodes", () => {
    it("returns an interface's numa node if it has no parents", () => {
      const nic = factory.machineInterface({
        numa_node: 2,
        parents: [],
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceNumaNodes(machine, nic)).toEqual([2]);
    });

    it("returns an interface's numa node via an alias", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [link],
        numa_node: 2,
        parents: [],
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceNumaNodes(machine, null, link)).toEqual([2]);
    });

    it("returns numa nodes of interface and its parents", () => {
      const interfaces = [
        factory.machineInterface({ numa_node: 1 }),
        factory.machineInterface({ numa_node: 3 }),
        factory.machineInterface({ numa_node: 0 }),
      ];
      const nic = factory.machineInterface({
        numa_node: 2,
        parents: [interfaces[0].id, interfaces[2].id],
      });
      interfaces.push(nic);
      const machine = factory.machineDetails({ interfaces });
      expect(getInterfaceNumaNodes(machine, nic)).toEqual([0, 1, 2]);
    });
  });

  describe("getInterfaceTypeText", () => {
    it("returns the text for a physical interface", () => {
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceTypeText(machine, nic)).toBe("Physical");
    });

    it("returns the text for a VLAN", () => {
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.VLAN,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceTypeText(machine, nic)).toBe("VLAN");
    });

    it("returns the text for an alias", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [factory.networkLink(), link],
        type: NetworkInterfaceTypes.VLAN,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceTypeText(machine, null, link)).toBe("Alias");
    });

    it("returns the interface type via an alias", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [link],
        type: NetworkInterfaceTypes.VLAN,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceTypeText(machine, null, link)).toBe("VLAN");
    });

    it("returns correct text if the bridge type is OVS", () => {
      const nic = factory.machineInterface({
        id: 100,
        params: { bridge_type: BridgeType.OVS },
        type: NetworkInterfaceTypes.BRIDGE,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceTypeText(machine, nic)).toBe("Open vSwitch");
    });

    it("returns correct text if the child bridge type is OVS", () => {
      const nic = factory.machineInterface({
        id: 100,
        children: [99],
      });
      const child = factory.machineInterface({
        id: 99,
        parents: [100],
        type: NetworkInterfaceTypes.BRIDGE,
        params: { bridge_type: BridgeType.OVS },
      });
      const machine = factory.machineDetails({ interfaces: [nic, child] });
      expect(getInterfaceTypeText(machine, nic)).toBe("Open vSwitch");
    });

    it("show the relationship if a physical interface has a child with bond type", () => {
      const child = factory.machineInterface({
        id: 99,
        parents: [100],
        type: NetworkInterfaceTypes.BOND,
      });
      const nic = factory.machineInterface({
        id: 100,
        children: [99],
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic, child] });
      expect(getInterfaceTypeText(machine, nic, null, true)).toBe(
        "Bonded physical"
      );
    });

    it("show the relationship if a physical interface has a child with bridge type", () => {
      const child = factory.machineInterface({
        id: 99,
        parents: [100],
        type: NetworkInterfaceTypes.BRIDGE,
      });
      const nic = factory.machineInterface({
        id: 100,
        children: [99],
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic, child] });
      expect(getInterfaceTypeText(machine, nic, null, true)).toBe(
        "Bridged physical"
      );
    });

    it("can not show the relationship if a physical interface has a child with bond type", () => {
      const child = factory.machineInterface({
        id: 99,
        parents: [100],
        type: NetworkInterfaceTypes.BOND,
      });
      const nic = factory.machineInterface({
        id: 100,
        children: [99],
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic, child] });
      expect(getInterfaceTypeText(machine, nic)).toBe("Physical");
    });

    it("can not show the relationship if a physical interface has a child with bridge type", () => {
      const child = factory.machineInterface({
        id: 99,
        parents: [100],
        type: NetworkInterfaceTypes.BRIDGE,
      });
      const nic = factory.machineInterface({
        id: 100,
        children: [99],
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic, child] });
      expect(getInterfaceTypeText(machine, nic)).toBe("Physical");
    });
  });

  describe("getRemoveTypeText", () => {
    it("returns the text for a physical interface", () => {
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getRemoveTypeText(machine, nic)).toBe("interface");
    });

    it("returns the text for a VLAN", () => {
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.VLAN,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getRemoveTypeText(machine, nic)).toBe("VLAN");
    });

    it("returns the text for other interfaces", () => {
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.BRIDGE,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getRemoveTypeText(machine, nic)).toBe("Bridge");
    });

    it("returns the text via an alias", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [link],
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getRemoveTypeText(machine, null, link)).toBe("interface");
    });
  });

  describe("isBootInterface", () => {
    it("checks if the nic is a boot interface", () => {
      const nic = factory.machineInterface({
        is_boot: true,
        type: NetworkInterfaceTypes.BRIDGE,
      });
      const machine = factory.machineDetails();
      expect(isBootInterface(machine, nic)).toBe(true);
    });

    it("checks that the nic is not an alias", () => {
      const nic = factory.machineInterface({
        is_boot: true,
        type: NetworkInterfaceTypes.ALIAS,
      });
      const machine = factory.machineDetails();
      expect(isBootInterface(machine, nic)).toBe(false);
    });

    it("checks parents for a boot interface", () => {
      const interfaces = [
        factory.machineInterface(),
        factory.machineInterface(),
        factory.machineInterface({ is_boot: true }),
      ];
      const nic = factory.machineInterface({
        is_boot: false,
        parents: [interfaces[0].id, interfaces[2].id],
        type: NetworkInterfaceTypes.BRIDGE,
      });
      interfaces.push(nic);
      const machine = factory.machineDetails({ interfaces });
      expect(isBootInterface(machine, nic)).toBe(true);
    });

    it("is not a boot interface if there are no parents with is_boot", () => {
      const interfaces = [
        factory.machineInterface({ is_boot: false }),
        factory.machineInterface(),
        factory.machineInterface({ is_boot: false }),
      ];
      const nic = factory.machineInterface({
        is_boot: false,
        parents: [interfaces[0].id, interfaces[2].id],
        type: NetworkInterfaceTypes.BRIDGE,
      });
      interfaces.push(nic);
      const machine = factory.machineDetails({ interfaces });
      expect(isBootInterface(machine, nic)).toBe(false);
    });

    it("checks if the nic is a boot interface via a link", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        is_boot: true,
        links: [link],
        type: NetworkInterfaceTypes.BRIDGE,
      });
      const machine = factory.machineDetails();
      expect(isBootInterface(machine, nic, link)).toBe(true);
    });
  });

  describe("isInterfaceConnected", () => {
    it("checks if the interface itself is connected", () => {
      const nic = factory.machineInterface({
        link_connected: true,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(isInterfaceConnected(machine, nic)).toBe(true);
    });

    it("checks if the interface itself is not connected", () => {
      const nic = factory.machineInterface({
        link_connected: false,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(isInterfaceConnected(machine, nic)).toBe(false);
    });

    it("checks the conncted status via a link", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        link_connected: true,
        links: [link],
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(isInterfaceConnected(machine, null, link)).toBe(true);
    });
  });

  describe("getLinkModeDisplay", () => {
    it("maps the link modes to display text", () => {
      expect(
        getLinkModeDisplay(factory.networkLink({ mode: NetworkLinkMode.AUTO }))
      ).toBe("Automatic");
      expect(
        getLinkModeDisplay(factory.networkLink({ mode: NetworkLinkMode.DHCP }))
      ).toBe("Dynamic");
      expect(
        getLinkModeDisplay(
          factory.networkLink({ mode: NetworkLinkMode.LINK_UP })
        )
      ).toBe("Unconfigured");
      expect(getLinkModeDisplay(null)).toBe("Unconfigured");
      expect(
        getLinkModeDisplay(
          factory.networkLink({ mode: NetworkLinkMode.STATIC })
        )
      ).toBe("Static (Client configured)");
    });
  });

  describe("getInterfaceDiscovered", () => {
    it("returns null if there is no discovered data", () => {
      const nic = factory.machineInterface({ discovered: null });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceDiscovered(machine, nic)).toBe(null);
    });

    it("gets the discovered data for the interface", () => {
      const discovered = factory.networkDiscoveredIP();
      const nic = factory.machineInterface({
        discovered: [discovered],
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceDiscovered(machine, nic)).toStrictEqual(discovered);
    });

    it("checks the conncted status via a link", () => {
      const discovered = factory.networkDiscoveredIP();
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        discovered: [discovered],
        links: [link],
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceDiscovered(machine, null, link)).toStrictEqual(
        discovered
      );
    });
  });

  describe("getInterfaceFabric", () => {
    it("can get a fabric", () => {
      const fabric = factory.fabric();
      const vlan = factory.vlan({ fabric: fabric.id });
      const nic = factory.machineInterface({
        vlan_id: vlan.id,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(getInterfaceFabric(machine, [fabric], [vlan], nic)).toStrictEqual(
        fabric
      );
    });

    it("can get a fabric from a link", () => {
      const fabric = factory.fabric();
      const vlan = factory.vlan({ fabric: fabric.id });
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [link],
        vlan_id: vlan.id,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(
        getInterfaceFabric(machine, [fabric], [vlan], null, link)
      ).toStrictEqual(fabric);
    });
  });

  describe("getInterfaceIPAddress", () => {
    it("can get a discovered ip address", () => {
      const discovered = factory.networkDiscoveredIP({ ip_address: "1.2.3.4" });
      const fabric = factory.fabric();
      const vlan = factory.vlan({ fabric: fabric.id });
      const nic = factory.machineInterface({
        discovered: [discovered],
        vlan_id: vlan.id,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(
        getInterfaceIPAddress(machine, [fabric], [vlan], nic)
      ).toStrictEqual("1.2.3.4");
    });

    it("can get an ip address from a link", () => {
      const fabric = factory.fabric();
      const vlan = factory.vlan({ fabric: fabric.id });
      const link = factory.networkLink({ ip_address: "1.2.3.4" });
      const nic = factory.machineInterface({
        links: [link],
        vlan_id: vlan.id,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(
        getInterfaceIPAddress(machine, [fabric], [vlan], null, link)
      ).toStrictEqual("1.2.3.4");
    });
  });

  describe("getInterfaceIPAddressOrMode", () => {
    it("can get a discovered ip address", () => {
      const discovered = factory.networkDiscoveredIP({ ip_address: "1.2.3.4" });
      const fabric = factory.fabric();
      const vlan = factory.vlan({ fabric: fabric.id });
      const nic = factory.machineInterface({
        discovered: [discovered],
        vlan_id: vlan.id,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(
        getInterfaceIPAddressOrMode(machine, [fabric], [vlan], nic)
      ).toStrictEqual("1.2.3.4");
    });

    it("can get an ip address from a link", () => {
      const fabric = factory.fabric();
      const vlan = factory.vlan({ fabric: fabric.id });
      const link = factory.networkLink({ ip_address: "1.2.3.4" });
      const nic = factory.machineInterface({
        links: [link],
        vlan_id: vlan.id,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(
        getInterfaceIPAddressOrMode(machine, [fabric], [vlan], null, link)
      ).toStrictEqual("1.2.3.4");
    });

    it("can get the link mode", () => {
      const fabric = factory.fabric();
      const vlan = factory.vlan({ fabric: fabric.id });
      const link = factory.networkLink({
        ip_address: "",
        mode: NetworkLinkMode.AUTO,
      });
      const nic = factory.machineInterface({
        links: [link],
        vlan_id: vlan.id,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(
        getInterfaceIPAddressOrMode(machine, [fabric], [vlan], null, link)
      ).toStrictEqual("Automatic");
    });
  });

  describe("getInterfaceSubnet", () => {
    it("can get a discovered subnet", () => {
      const subnet = factory.subnet();
      const discovered = factory.networkDiscoveredIP({ subnet_id: subnet.id });
      const fabric = factory.fabric();
      const vlan = factory.vlan({ fabric: fabric.id });
      const nic = factory.machineInterface({
        discovered: [discovered],
        vlan_id: vlan.id,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(
        getInterfaceSubnet(machine, [subnet], [fabric], [vlan], true, nic)
      ).toStrictEqual(subnet);
    });

    it("does not get the discovered subnet when networking is enabled", () => {
      const subnet = factory.subnet();
      const discovered = factory.networkDiscoveredIP({ subnet_id: subnet.id });
      const fabric = factory.fabric();
      const vlan = factory.vlan({ fabric: fabric.id });
      const nic = factory.machineInterface({
        discovered: [discovered],
        vlan_id: vlan.id,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(
        getInterfaceSubnet(machine, [subnet], [fabric], [vlan], false, nic)
      ).toBe(null);
    });

    it("can get a subnet from a link", () => {
      const subnet = factory.subnet();
      const fabric = factory.fabric();
      const vlan = factory.vlan({ fabric: fabric.id });
      const link = factory.networkLink({ subnet_id: subnet.id });
      const nic = factory.machineInterface({
        links: [link],
        vlan_id: vlan.id,
      });
      const machine = factory.machineDetails({ interfaces: [nic] });
      expect(
        getInterfaceSubnet(
          machine,
          [subnet],
          [fabric],
          [vlan],
          true,
          null,
          link
        )
      ).toStrictEqual(subnet);
    });
  });

  describe("getNextNicName", () => {
    describe("physical", () => {
      it("can get the next physical nic name", () => {
        const machine = factory.machineDetails({
          interfaces: [factory.machineInterface({ name: "eth0" })],
        });
        expect(
          getNextNicName(machine, NetworkInterfaceTypes.PHYSICAL)
        ).toStrictEqual("eth1");
      });

      it("can get the next physical nic name when there are no existing nics", () => {
        const machine = factory.machineDetails({ interfaces: [] });
        expect(
          getNextNicName(machine, NetworkInterfaceTypes.PHYSICAL)
        ).toStrictEqual("eth0");
      });

      it("can get the next physical nic name when the names are out of order", () => {
        const machine = factory.machineDetails({
          interfaces: [
            factory.machineInterface({ name: "eth1" }),
            factory.machineInterface({ name: "eth12" }),
            factory.machineInterface({ name: "eth5" }),
          ],
        });
        expect(
          getNextNicName(machine, NetworkInterfaceTypes.PHYSICAL)
        ).toStrictEqual("eth13");
      });

      it("can get the next physical nic name when there are non sequential names", () => {
        const machine = factory.machineDetails({
          interfaces: [
            factory.machineInterface({ name: "eth1" }),
            factory.machineInterface({ name: "ethernetsix" }),
          ],
        });
        expect(
          getNextNicName(machine, NetworkInterfaceTypes.PHYSICAL)
        ).toStrictEqual("eth2");
      });

      it("can get the next physical nic name when there are partial names", () => {
        const machine = factory.machineDetails({
          interfaces: [
            factory.machineInterface({ name: "eth1" }),
            factory.machineInterface({ name: "eth" }),
          ],
        });
        expect(
          getNextNicName(machine, NetworkInterfaceTypes.PHYSICAL)
        ).toStrictEqual("eth2");
      });

      it("can get the next physical nic name when there are partial similar", () => {
        const machine = factory.machineDetails({
          interfaces: [
            factory.machineInterface({ name: "eth1" }),
            factory.machineInterface({ name: "eth3eth3" }),
          ],
        });
        expect(
          getNextNicName(machine, NetworkInterfaceTypes.PHYSICAL)
        ).toStrictEqual("eth2");
      });
    });

    describe("bond", () => {
      it("can get the next physical nic name", () => {
        const machine = factory.machineDetails({
          interfaces: [factory.machineInterface({ name: "bond0" })],
        });
        expect(
          getNextNicName(machine, NetworkInterfaceTypes.BOND)
        ).toStrictEqual("bond1");
      });

      it("can get the next physical nic name when there are no existing nics", () => {
        const machine = factory.machineDetails({ interfaces: [] });
        expect(
          getNextNicName(machine, NetworkInterfaceTypes.BOND)
        ).toStrictEqual("bond0");
      });
    });

    describe("bridge", () => {
      it("can get the next physical nic name", () => {
        const machine = factory.machineDetails({
          interfaces: [factory.machineInterface({ name: "br0" })],
        });
        expect(
          getNextNicName(machine, NetworkInterfaceTypes.BRIDGE)
        ).toStrictEqual("br1");
      });

      it("can get the next physical nic name when there are no existing nics", () => {
        const machine = factory.machineDetails({ interfaces: [] });
        expect(
          getNextNicName(machine, NetworkInterfaceTypes.BRIDGE)
        ).toStrictEqual("br0");
      });
    });

    describe("alias", () => {
      it("can get the next alias name", () => {
        const nic = factory.machineInterface({
          links: [factory.networkLink()],
          name: "eth0",
        });
        const machine = factory.machineDetails({
          interfaces: [nic],
        });
        expect(
          getNextNicName(machine, NetworkInterfaceTypes.ALIAS, nic)
        ).toStrictEqual("eth0:1");
      });
    });

    describe("VLAN", () => {
      it("can get the next vlan name", () => {
        const nic = factory.machineInterface({
          name: "eth0",
        });
        const machine = factory.machineDetails({
          interfaces: [nic],
        });
        expect(
          getNextNicName(machine, NetworkInterfaceTypes.VLAN, nic, 5)
        ).toStrictEqual("eth0.5");
      });
    });
  });

  describe("canAddAlias", () => {
    it("can not add an alias if the nic is an alias", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [factory.networkLink(), link],
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({
        interfaces: [nic],
      });
      expect(canAddAlias(machine, nic, link)).toBe(false);
    });

    it("can not add an alias if there are no links", () => {
      const nic = factory.machineInterface({
        links: [],
        type: NetworkInterfaceTypes.ALIAS,
      });
      const machine = factory.machineDetails({
        interfaces: [nic],
      });
      expect(canAddAlias(machine, nic)).toBe(false);
    });

    it("can not add an alias if the first link is LINK_UP", () => {
      const nic = factory.machineInterface({
        links: [factory.networkLink({ mode: NetworkLinkMode.LINK_UP })],
        type: NetworkInterfaceTypes.ALIAS,
      });
      const machine = factory.machineDetails({
        interfaces: [nic],
      });
      expect(canAddAlias(machine, nic)).toBe(false);
    });

    it("can add an alias", () => {
      const nic = factory.machineInterface({
        links: [factory.networkLink({ mode: NetworkLinkMode.AUTO })],
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const machine = factory.machineDetails({
        interfaces: [nic],
      });
      expect(canAddAlias(machine, nic)).toBe(true);
    });
  });

  describe("getLinkFromNic", () => {
    it("can retrieve a link from a nic", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [factory.networkLink(), link],
      });
      expect(getLinkFromNic(nic, link.id)).toStrictEqual(link);
    });

    it("handles no links found", () => {
      const nic = factory.machineInterface({
        links: [],
      });
      expect(getLinkFromNic(nic, 5)).toBe(null);
    });
  });

  describe("getInterfaceById", () => {
    it("can retrieve a nic from a link id", () => {
      const link = factory.networkLink();
      const nic = factory.machineInterface({
        links: [factory.networkLink(), link],
      });
      const machine = factory.machineDetails({
        interfaces: [nic],
      });
      expect(getInterfaceById(machine, null, link.id)).toStrictEqual(nic);
    });

    it("can retrieve a nic from a nic id", () => {
      const nic = factory.machineInterface({
        links: [],
      });
      const machine = factory.machineDetails({
        interfaces: [nic],
      });
      expect(getInterfaceById(machine, nic.id)).toStrictEqual(nic);
    });
  });
});
