import type { Fabric } from "@/app/store/fabric/types";

/**
 * Get the Fabric display text.
 * @param vlan - A VLAN.
 * @return The VLAN display text.
 */
export const getFabricDisplay = (
  fabric: Fabric | null | undefined
): string | null => {
  if (!fabric) {
    return null;
  }
  if (fabric.name) {
    return fabric.name;
  } else {
    return `fabric-${fabric.id}`;
  }
};

/**
 * Get a fabric with a given id
 * @param fabrics - The fabrics to check.
 * @param fabricId - Fabric id
 * @returns fabric with a given id
 */
export const getFabricById = (
  fabrics: Fabric[],
  fabricId: Fabric["id"]
): Fabric | null => fabrics.find((fabric) => fabric?.id === fabricId) || null;
