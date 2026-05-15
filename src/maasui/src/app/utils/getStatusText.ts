import type { Host } from "@/app/store/types/host";
import { NodeStatusCode } from "@/app/store/types/node";

// Node statuses for which the OS + release is made human-readable.
const formattedReleaseStatuses = [
  NodeStatusCode.DEPLOYED,
  NodeStatusCode.DEPLOYING,
];

/**
 * Returns formatted status text of a given node.
 * @param node - the node who's status you are checking.
 * @param release - the formatted release of the node.
 * @returns formatted status text
 */
export const getStatusText = (node: Host | null, release: string): string => {
  if (!node) {
    return "Unknown";
  }
  if (release && formattedReleaseStatuses.includes(node.status_code)) {
    return node.status_code === NodeStatusCode.DEPLOYING
      ? `Deploying ${release}`
      : release;
  }
  return node.status;
};
