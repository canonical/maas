import type { Space } from "@/app/store/space/types";
import type { Subnet, SubnetDetails, SubnetIP } from "@/app/store/subnet/types";
import { IPAddressType } from "@/app/store/subnet/types";
import { NodeType } from "@/app/store/types/node";
import { getNodeTypeDisplay } from "@/app/store/utils";
import type { VLAN } from "@/app/store/vlan/types";

/**
 * Get the Subnet display text.
 * @param subnet - A subnet.
 * @return The subnet display text.
 */
export const getSubnetDisplay = (
  subnet: Subnet | null | undefined,
  short?: boolean
): string => {
  if (!subnet) {
    return "Unconfigured";
  } else if (!short && subnet.cidr !== subnet.name) {
    return `${subnet.cidr} (${subnet.name})`;
  } else {
    return subnet.cidr;
  }
};

/**
 * Returns whether a subnet is of type SubnetDetails.
 * @param subnet - The subnet to check.
 * @returns Whether the subnet is of type SubnetDetails.
 */
export const isSubnetDetails = (
  subnet?: Subnet | null
): subnet is SubnetDetails => !!subnet && "ip_addresses" in subnet;

/**
 * Get the Subnet available IPs.
 * @param subnet - A subnet.
 * @return Subnet's available IPs string, e.g. "100%"
 */
export const getAvailableIPs = (subnet: Subnet | null | undefined): string => {
  if (!subnet) {
    return "Unconfigured";
  } else {
    return `${subnet?.statistics?.available_string}`;
  }
};

/**
 * Get Subnets for a given VLAN id
 * @param subnets - Subnets.
 * @param vlanId - VLAN id.
 * @return Subnets for a given VLAN id
 */
export const getSubnetsInVLAN = (
  subnets: Subnet[],
  vlanId: VLAN["id"]
): Subnet[] => subnets.filter((subnet) => subnet.vlan === vlanId);

/**
 * Get subnets in a given space
 * @param subnets - The subnets to check.
 * @param spaceId - Space id
 * @returns subnets in a given space.
 */
export const getSubnetsInSpace = (
  subnets: Subnet[],
  spaceId: Space["id"]
): Subnet[] => subnets.filter((subnet) => subnet.space === spaceId);

/**
 * Returns whether a subnet has IP addresses
 * @param subnet - The subnet to check.
 * @returns Whether the given subnet has IP addresses.
 */
export const getHasIPAddresses = (subnet?: Subnet | null): boolean =>
  isSubnetDetails(subnet) ? subnet.ip_addresses.length > 0 : false;

/**
 * Returns whether a subnet can be used as the destination of a source subnet.
 * @param destination - The destination subnet.
 * @param source - The source subnet.
 * @returns Whether the subnet can be used as a destnation for the source.
 */
export const getIsDestinationForSource = (
  destination: Subnet,
  source: Subnet | null
): boolean =>
  destination.id !== source?.id && destination.version === source?.version;

/**
 * Get the IP address type display text.
 * @param ipAddressType - The IP address type to check.
 * @returns IP address type display text.
 */
export const getIPTypeDisplay = (ipAddressType: IPAddressType): string => {
  switch (ipAddressType) {
    case IPAddressType.AUTO:
      return "Automatic";
    case IPAddressType.DHCP:
      return "DHCP";
    case IPAddressType.DISCOVERED:
      return "Discovered";
    case IPAddressType.STICKY:
      return "Sticky";
    case IPAddressType.USER_RESERVED:
      return "User reserved";
    default:
      return "Unknown";
  }
};

/**
 * Get the IP address usage display text.
 * @param ipAddress - The IP address to check.
 * @returns IP address usage display text.
 */
export const getIPUsageDisplay = (ipAddress: SubnetIP): string => {
  if (ipAddress.node_summary) {
    const { is_container, node_type } = ipAddress.node_summary;
    if (node_type === NodeType.DEVICE && is_container) {
      return "Container";
    }
    return getNodeTypeDisplay(node_type);
  }
  if (ipAddress.bmcs?.length) {
    return "BMC";
  }
  if (ipAddress.dns_records?.length) {
    return "DNS";
  }
  return "Unknown";
};
