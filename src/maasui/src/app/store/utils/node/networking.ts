import { isNodeDetails } from "./base";

import type { Fabric } from "@/app/store/fabric/types";
import type { Subnet } from "@/app/store/subnet/types";
import {
  BridgeType,
  NetworkInterfaceTypes,
  NetworkLinkMode,
} from "@/app/store/types/enum";
import type {
  NetworkInterface,
  NetworkLink,
  DiscoveredIP,
  Node,
  NodeDetails,
} from "@/app/store/types/node";
import type { VLAN } from "@/app/store/vlan/types";
import { getNextName } from "@/app/utils";

export const INTERFACE_TYPE_DISPLAY = {
  [NetworkInterfaceTypes.PHYSICAL]: "Physical",
  [NetworkInterfaceTypes.BOND]: "Bond",
  [NetworkInterfaceTypes.BRIDGE]: "Bridge",
  [NetworkInterfaceTypes.VLAN]: "VLAN",
  [NetworkInterfaceTypes.ALIAS]: "Alias",
  [BridgeType.OVS]: "Open vSwitch",
};

/**
 * Get the link's interface and position by a link's ID.
 * @param node - The nic's node.
 * @param linkId - A link's ID.
 * @return The link's interface and position.
 */
export const getLinkInterfaceById = (
  node: Node,
  linkId?: NetworkLink["id"] | null
): [NodeDetails["interfaces"][0] | null, number | null] => {
  if (!linkId || !isNodeDetails(node)) {
    return [null, null];
  }
  for (let i = 0; i < node.interfaces.length; i++) {
    const links = node.interfaces[i].links;
    for (let j = 0; j < links.length; j++) {
      if (links[j].id === linkId) {
        return [node.interfaces[i], j];
      }
    }
  }
  return [null, null];
};

/**
 * Get the link's interface and position.
 * @param node - The nic's node.
 * @param link - A link to an interface.
 * @return The link's interface and position.
 */
export const getLinkInterface = (
  node: Node,
  link?: NetworkLink | null
): [NetworkInterface | null, number | null] => {
  return getLinkInterfaceById(node, link?.id);
};

/**
 * Get an interface by id.
 * @param node - The nic's node.
 * @param linkId - A link's ID.
 * @return An interface.
 */
export const getInterfaceById = <N extends NodeDetails>(
  node?: N | null,
  interfaceId?: Node["id"] | null,
  linkId?: NetworkLink["id"] | null
): N["interfaces"][0] | null => {
  if (!isNodeDetails(node) || (!linkId && !interfaceId)) {
    return null;
  }
  if (linkId && !interfaceId) {
    const [nic] = getLinkInterfaceById(node, linkId);
    return nic;
  }
  return node.interfaces.find(({ id }) => id === interfaceId) || null;
};

/**
 * Whether an interface is an alias.
 * @param node - The nic's node.
 * @param link - A link to an interface.
 * @return Whether this is an alias.
 */
export const isAlias = (node: Node, link?: NetworkLink | null): boolean => {
  const [, linkIndex] = getLinkInterface(node, link);
  // The first link provides supplementary data for the non-alias interface.
  return !!link && typeof linkIndex === "number" && linkIndex > 0;
};

/**
 * Get the name of an interface.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return The interface's name.
 */
export const getInterfaceName = (
  node: Node,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): string => {
  let linkIndex: number | null = null;
  if (link) {
    [nic, linkIndex] = getLinkInterface(node, link);
  }
  if (!nic) {
    return "";
  }
  return link && isAlias(node, link) && linkIndex
    ? `${nic.name}:${linkIndex}`
    : nic.name;
};

/**
 * Get the type of an interface.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return The interface type.
 */
export const getInterfaceType = (
  node: Node,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): NetworkInterfaceTypes | null => {
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  return link && isAlias(node, link)
    ? NetworkInterfaceTypes.ALIAS
    : nic?.type || null;
};

/**
 * Check if an interface has a certain type or types.
 * @param interfaceType - A single or array of interface types.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return Whether the interface's type matches those supplied.
 */
export const hasInterfaceType = (
  interfaceType: NetworkInterfaceTypes | NetworkInterfaceTypes[],
  node: Node,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): boolean => {
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  const nicOrLinkType = getInterfaceType(node, nic, link);
  return (
    !!nicOrLinkType &&
    (Array.isArray(interfaceType) ? interfaceType : [interfaceType]).includes(
      nicOrLinkType
    )
  );
};

/**
 * Get the mode for a link.
 * @param link - A link to an interface.
 * @return The interface mode.
 */
export const getLinkMode = (link?: NetworkLink | null): NetworkLink["mode"] => {
  // If the interface is either disabled or has no links it means the interface
  // is in LINK_UP mode.
  return link?.mode || NetworkLinkMode.LINK_UP;
};

/**
 * Get the parents for a bond or bridge interface.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return The parents for a bond or bridge interface.
 */
export const getBondOrBridgeParents = (
  node: Node,
  nic: NetworkInterface | null,
  link?: NetworkLink | null
): NetworkInterface[] => {
  if (
    !nic ||
    !isNodeDetails(node) ||
    !hasInterfaceType(
      [NetworkInterfaceTypes.BOND, NetworkInterfaceTypes.BRIDGE],
      node,
      nic,
      link
    )
  ) {
    return [];
  }
  return nic.parents.reduce<NetworkInterface[]>((parents, parent) => {
    const match = node.interfaces.find(({ id }) => id && id === parent);
    if (match) {
      parents.push(match);
    }
    return parents;
  }, []);
};

/**
 * Get the interface that joins parents of a bond or bridge.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @return The interface that joins bond or bridge interfaces.
 */
const findBondOrBridgeChild = (
  node: Node,
  nic?: NetworkInterface | null
): NetworkInterface | null => {
  if (!nic || !isNodeDetails(node)) {
    return null;
  }
  let bondOrBridgeChild: NetworkInterface | null = null;
  nic.children.some((childId) => {
    // Get the interface that has the child id.
    const child = node.interfaces.find(({ id }) => id === childId);
    if (!child) {
      return false;
    }
    if (
      [NetworkInterfaceTypes.BOND, NetworkInterfaceTypes.BRIDGE].includes(
        child.type
      )
    ) {
      // This is a bond or bridge child so store the interface.
      bondOrBridgeChild = child;
    }
    // Exit the loop if a match was found.
    return !!bondOrBridgeChild;
  });
  return bondOrBridgeChild;
};

/**
 * Get the interface that joins parents of a bond or bridge.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return The interface that joins bond or bridge interfaces.
 */
export const getBondOrBridgeChild = (
  node: Node,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): NetworkInterface | null => {
  if (!isBondOrBridgeParent(node, nic, link)) {
    return null;
  }
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  return findBondOrBridgeChild(node, nic);
};

/**
 * Check if an interface is a parent of a bond or bridge.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return Whether an interface is a parent of a bond or bridge.
 */
export const isBondOrBridgeParent = (
  node: Node,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): boolean => {
  if (link && isAlias(node, link)) {
    // Aliases can't be bond or bridge parents.
    return false;
  }
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  if (!nic) {
    return false;
  }
  const child = findBondOrBridgeChild(node, nic);
  if (child) {
    return hasInterfaceType(
      [NetworkInterfaceTypes.BOND, NetworkInterfaceTypes.BRIDGE],
      node,
      child
    );
  }
  return false;
};

/**
 * Check if an interface is a bond or bridge child.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return Whether an interface is a bond or bridge child.
 */
export const isBondOrBridgeChild = (
  node: Node,
  nic: NetworkInterface | null,
  link?: NetworkLink | null
): boolean => {
  if (link && isAlias(node, link)) {
    // Aliases can't be bond or bridge children.
    return false;
  }
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  // A bond or bridge child must have at least one parent.
  if (!nic || nic.parents.length === 0) {
    return false;
  }
  return hasInterfaceType(
    [NetworkInterfaceTypes.BOND, NetworkInterfaceTypes.BRIDGE],
    node,
    nic
  );
};

/**
 * Get the numa nodes for an interface.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return The numa nodes for the interface.
 */
export const getInterfaceNumaNodes = (
  node: Node,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): NetworkInterface["numa_node"][] | null => {
  if (!isNodeDetails(node)) {
    return null;
  }
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  if (!nic) {
    return null;
  }
  if (!nic.parents?.length) {
    return [nic.numa_node];
  }
  const allNumas = nic.parents.reduce(
    (parents, parent) => {
      const parentInterface = node.interfaces.find(
        ({ id }) => id && id === parent
      );
      if (parentInterface && !parents.includes(parentInterface.numa_node)) {
        parents.push(parentInterface.numa_node);
      }
      return parents;
    },
    nic.numa_node ? [nic.numa_node] : []
  );
  return allNumas.sort((a, b) => a - b);
};

/**
 * Get the text for the type of the interface.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @param showRelationship - Whether to show the relationship with the child.
 * @return The text for the interface type.
 */
export const getInterfaceTypeText = (
  node: Node,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null,
  showRelationship = false
): string | null => {
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  if (!nic) {
    return null;
  }
  const child = getBondOrBridgeChild(node, nic, link);
  let interfaceType: BridgeType.OVS | NetworkInterfaceTypes | null = null;
  if (
    (nic.type === NetworkInterfaceTypes.BRIDGE &&
      nic.params?.bridge_type === BridgeType.OVS) ||
    (child?.type === NetworkInterfaceTypes.BRIDGE &&
      child?.params?.bridge_type === BridgeType.OVS)
  ) {
    // If this interface or its child is an OVS bridge then display it as such.
    interfaceType = BridgeType.OVS;
  } else if (
    showRelationship &&
    child &&
    nic.type === NetworkInterfaceTypes.PHYSICAL
  ) {
    // If this is a physical interface that has a child then show the relationship.
    switch (child.type) {
      case NetworkInterfaceTypes.BOND:
        return "Bonded physical";
      case NetworkInterfaceTypes.BRIDGE:
        return "Bridged physical";
    }
  } else {
    // Get the type for all other interfaces
    interfaceType = getInterfaceType(node, nic, link);
  }
  return interfaceType ? INTERFACE_TYPE_DISPLAY[interfaceType] : null;
};

/**
 * Check the interface is the boot interface or has a parent
 * that is a boot interface.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return Whether this is a boot interface.
 */
export const isBootInterface = (
  node: Node,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): boolean => {
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  if (!nic || !node) {
    return false;
  }
  if (
    nic.is_boot &&
    !hasInterfaceType(NetworkInterfaceTypes.ALIAS, node, nic, link)
  ) {
    return true;
  }
  const parents = getBondOrBridgeParents(node, nic, link);
  return parents.some(({ is_boot }) => is_boot);
};

/**
 * Check if an interface is connected.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return Whether an interface is connected.
 */
export const isInterfaceConnected = (
  node: Node,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): boolean => {
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  if (!nic) {
    return false;
  }
  return nic.link_connected;
};

export const LINK_MODE_DISPLAY = {
  [NetworkLinkMode.AUTO]: "Automatic",
  [NetworkLinkMode.DHCP]: "Dynamic",
  [NetworkLinkMode.LINK_UP]: "Unconfigured",
  [NetworkLinkMode.STATIC]: "Static (Client configured)",
};

/**
 * Get the text for the link mode of the interface.
 * @param link - A link to an interface.
 * @return The display text for a link mode.
 */
export const getLinkModeDisplay = (
  link?: NetworkLink | null
): string | null => {
  const mode = link ? getLinkMode(link) : null;
  return mode ? LINK_MODE_DISPLAY[mode] || mode : "Unconfigured";
};

/**
 * Gets the discovered data for an interface.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return The discovered data for the interface.
 */
export const getInterfaceDiscovered = (
  node: Node,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): DiscoveredIP | null => {
  if (!isNodeDetails(node)) {
    return null;
  }
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  // The interface uses the first discovered data.
  return nic?.discovered?.length ? nic.discovered[0] : null;
};
/**
 * Get the fabric for an interface.
 * @param node - The nic's node.
 * @param fabrics - The available fabrics.
 * @param vlans - The available VLANs.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return The fabric for the interface.
 */
export const getInterfaceFabric = (
  node: Node,
  fabrics: Fabric[],
  vlans: VLAN[],
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): Fabric | null => {
  if (!isNodeDetails(node)) {
    return null;
  }
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  if (!nic) {
    return null;
  }
  const vlan = vlans.find(({ id }) => id === nic?.vlan_id);
  if (!vlan) {
    return null;
  }
  return fabrics.find(({ id }) => id === vlan?.fabric) || null;
};

/**
 * Get the IP address for an interface.
 * @param node - The nic's node.
 * @param fabrics - The available fabrics.
 * @param vlans - The available VLANs.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return The IP address for the interface.
 */
export const getInterfaceIPAddress = (
  node: Node,
  fabrics: Fabric[],
  vlans: VLAN[],
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): DiscoveredIP["ip_address"] | NetworkLink["ip_address"] | null => {
  if (!isNodeDetails(node)) {
    return null;
  }
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  if (!nic) {
    return null;
  }
  const fabric = getInterfaceFabric(node, fabrics, vlans, nic, link);
  const discovered = getInterfaceDiscovered(node, nic, link);
  const discoveredIP = discovered?.ip_address;
  if (!fabric) {
    return null;
  }
  if (discoveredIP) {
    return discoveredIP;
  }
  return link?.ip_address;
};

/**
 * Get the IP address or link mode for an interface.
 * @param node - The nic's node.
 * @param fabrics - The available fabrics.
 * @param vlans - The available VLANs.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return The IP address or link mode for the interface.
 */
export const getInterfaceIPAddressOrMode = (
  node: Node,
  fabrics: Fabric[],
  vlans: VLAN[],
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): DiscoveredIP["ip_address"] | NetworkLink["ip_address"] | null => {
  const ipAddress = getInterfaceIPAddress(node, fabrics, vlans, nic, link);
  const discovered = getInterfaceDiscovered(node, nic, link);
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  if (!nic) {
    return null;
  }
  const fabric = getInterfaceFabric(node, fabrics, vlans, nic, link);
  const hasDiscoveredIP = !!discovered?.ip_address;
  if (fabric && hasDiscoveredIP) {
    return ipAddress;
  } else if (!hasDiscoveredIP) {
    return ipAddress || getLinkModeDisplay(link);
  }
  return null;
};

/**
 * Get the subnet for an interface.
 * @param node - The nic's node.
 * @param subnets - The available subnets.
 * @param fabrics - The available fabrics.
 * @param vlans - The available VLANs.
 * @param isAllNetworkingDisabled - Whether all networking is disabled.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return The subnet for the interface.
 */
export const getInterfaceSubnet = (
  node: Node,
  subnets: Subnet[],
  fabrics: Fabric[],
  vlans: VLAN[],
  isAllNetworkingDisabled: boolean,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): Subnet | null => {
  if (!isNodeDetails(node)) {
    return null;
  }
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  if (!nic) {
    return null;
  }
  const fabric = getInterfaceFabric(node, fabrics, vlans, nic, link);
  const discovered = getInterfaceDiscovered(node, nic, link);
  const discoveredSubnetId = discovered?.subnet_id || null;
  let subnetId: Subnet["id"] | null | undefined;
  if (fabric && !discoveredSubnetId) {
    subnetId = link?.subnet_id;
  } else if (isAllNetworkingDisabled && discoveredSubnetId) {
    subnetId = discoveredSubnetId;
  } else {
    return null;
  }
  return subnets.find(({ id }) => id === subnetId) || null;
};

/**
 * Get the text to use for the remove link and message.
 * @param node - The nic's node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return The type text to use when removing the interface.
 */
export const getRemoveTypeText = (
  node: Node,
  nic: NetworkInterface | null,
  link?: NetworkLink | null
): string | null => {
  const interfaceType = getInterfaceType(node, nic, link);
  if (interfaceType === NetworkInterfaceTypes.PHYSICAL) {
    return "interface";
  } else if (interfaceType === NetworkInterfaceTypes.VLAN) {
    return "VLAN";
  } else {
    return getInterfaceTypeText(node, nic, link);
  }
};

/**
 * Find the next available name for an interface.
 * @param node - A node.
 * @param interfaceType - A network interface type.
 * @param nic - A network interface.
 * @param vlan - A VLAN.
 * @return An available name.
 */
export const getNextNicName = (
  node: Node | null | undefined,
  interfaceType: NetworkInterfaceTypes,
  nic?: NetworkInterface | null,
  vid?: VLAN["vid"] | null
): string | null => {
  if (!isNodeDetails(node)) {
    return null;
  }
  if (
    [NetworkInterfaceTypes.ALIAS, NetworkInterfaceTypes.VLAN].includes(
      interfaceType
    )
  ) {
    // A nic is required when determining the next alias or vlan name.
    if (!nic) {
      return null;
    }
    if (interfaceType === NetworkInterfaceTypes.ALIAS) {
      return `${nic.name}:${nic.links.length}`;
    }
    if (interfaceType === NetworkInterfaceTypes.VLAN) {
      // VLANs require a vid for the name.
      if (vid === undefined || vid === null) {
        return null;
      }
      return `${nic.name}.${vid}`;
    }
  }
  let prefix = "";
  switch (interfaceType) {
    case NetworkInterfaceTypes.BOND:
      prefix = "bond";
      break;
    case NetworkInterfaceTypes.BRIDGE:
      prefix = "br";
      break;
    case NetworkInterfaceTypes.PHYSICAL:
      prefix = "eth";
      break;
  }
  if (!prefix) {
    return null;
  }
  const names = node.interfaces.map(({ name }) => name);
  return getNextName(names, prefix);
};

/**
 * Check if an alias can be added to the interface.
 * @param node - A node.
 * @param nic - A network interface.
 * @param link - A link to an interface.
 * @return An available name.
 */
export const canAddAlias = (
  node?: Node | null,
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): boolean =>
  !!node &&
  !!nic &&
  !hasInterfaceType(NetworkInterfaceTypes.ALIAS, node, nic, link) &&
  nic.links.length > 0 &&
  getLinkMode(nic.links[0]) !== NetworkLinkMode.LINK_UP;

/**
 * Find a link on an interface.
 * @param nic - A network interface.
 * @param linkId - A link id.
 * @return A link.
 */
export const getLinkFromNic = (
  nic?: NetworkInterface | null,
  linkId?: NetworkLink["id"] | null
): NetworkLink | null =>
  linkId ? nic?.links.find(({ id }) => id === linkId) || null : null;
