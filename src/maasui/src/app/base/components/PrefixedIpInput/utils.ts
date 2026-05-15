import { isIPv4 } from "is-ip";

import {
  getImmutableAndEditableOctets,
  getIpRangeFromCidr,
} from "@/app/utils/subnetIpRange";

/**
 * Formats the PrefixedIpInput value into a complete IP address.
 *
 * @param ip The partial IP address to format
 * @param cidr The subnet's CIDR notation
 * @returns The formatted IP address
 */
export const formatIpAddress = (
  ip: string | undefined,
  cidr: string
): string => {
  const [startIp, endIp] = getIpRangeFromCidr(cidr);
  const [immutableOctets, _] = getImmutableAndEditableOctets(startIp, endIp);
  const networkAddress = cidr.split("/")[0];
  const ipv6Prefix = networkAddress.substring(
    0,
    networkAddress.lastIndexOf(":")
  );
  const subnetIsIpv4 = isIPv4(networkAddress);

  return subnetIsIpv4 ? `${immutableOctets}.${ip}` : `${ipv6Prefix}${ip}`;
};
