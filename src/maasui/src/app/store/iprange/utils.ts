import type { IPRange } from "./types";
import { IPRangeType } from "./types";

/**
 * Get whether an IP range is dynamic.
 * @param ipRange - The IP range to check.
 * @returns Whether the IP range is dynamic.
 */
export const isDynamic = (ipRange: IPRange): boolean =>
  ipRange.type === IPRangeType.Dynamic;

/**
 * Get comment text for an IP range.
 * @param ipRange - The IP range to check.
 * @returns Comment text for an IP range.
 */
export const getCommentDisplay = (ipRange: IPRange): string =>
  isDynamic(ipRange) ? "Dynamic" : ipRange.comment || "—";

/**
 * Get owner text for an IP range.
 * @param ipRange - The IP range to check.
 * @returns Owner text for an IP range.
 */
export const getOwnerDisplay = (ipRange: IPRange): string =>
  isDynamic(ipRange) ? "MAAS" : ipRange.user;

/**
 * Get type text for an IP range.
 * @param ipRange - The IP range to check.
 * @returns Type text for an IP range.
 */
export const getTypeDisplay = (ipRange: IPRange): string =>
  isDynamic(ipRange) ? "Dynamic" : "Reserved";

/**
 * Get display name for an IP range.
 * @param ipRange - The IP range to check.
 * @returns Display name text for an IP range.
 */
export const getIpRangeDisplayName = (ipRange?: IPRange): string =>
  ipRange ? `${ipRange?.start_ip} - ${ipRange?.end_ip}` : "";
