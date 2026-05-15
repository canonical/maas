import type { Fabric } from "@/app/store/fabric/types";
import { getFabricDisplay } from "@/app/store/fabric/utils";
import type { VLAN, VLANDetails } from "@/app/store/vlan/types";
import { VlanVid } from "@/app/store/vlan/types";

/**
 * Get the VLAN display text.
 * @param vlan - A VLAN.
 * @return The VLAN display text.
 */
export const getVLANDisplay = (
  vlan: VLAN | null | undefined
): string | null => {
  if (!vlan) {
    return null;
  }
  if (vlan.vid === VlanVid.UNTAGGED) {
    return "untagged";
  } else if (vlan.name) {
    return `${vlan.vid} (${vlan.name})`;
  } else {
    return vlan.vid.toString();
  }
};

/**
 * Get the text full name for a VLAN.
 * @param vlanId - A VLAN's id.
 * @param vlans - The available vlans.
 * @param fabrics - The available fabrics.
 * @return A VLAN's full name.
 */
export const getFullVLANName = (
  vlanId: VLAN["id"],
  vlans: VLAN[],
  fabrics: Fabric[]
): string | null => {
  const vlan = vlans.find(({ id }) => id === vlanId);
  if (!vlan) {
    return null;
  }
  const fabric = fabrics.find(({ id }) => id === vlan.fabric);
  if (!fabric) {
    return null;
  }
  return `${getFabricDisplay(fabric)}.${getVLANDisplay(vlan)}`;
};

/**
 * Get the text for the link mode of the interface.
 * @param vlan - A VLAN.
 * @param vlans - The available vlans.
 * @param fabrics - The available fabrics.
 * @param showVLANName - Whether to show the relayed VLAN's name.
 * @return The display text for a link mode.
 */
export const getDHCPStatus = (
  vlan: VLAN | null | undefined,
  vlans: VLAN[],
  fabrics: Fabric[],
  showVLANName = false
): string => {
  if (vlan?.external_dhcp) {
    return `External (${vlan.external_dhcp})`;
  }
  if (vlan?.dhcp_on) {
    return "MAAS-provided";
  }
  if (vlan?.relay_vlan) {
    if (showVLANName) {
      return `Relayed via ${getFullVLANName(vlan.relay_vlan, vlans, fabrics)}`;
    } else {
      return "Relayed";
    }
  }
  return "No DHCP";
};

/**
 * Returns whether a VLAN is of type VLANDetails.
 * @param vlan - The VLAN to check.
 * @returns Whether the VLAN is of type VLANDetails.
 */
export const isVLANDetails = (vlan?: VLAN | null): vlan is VLANDetails =>
  !!vlan && "space_ids" in vlan;

/**
 * Returns VLANs for a given fabric id.
 * @param vlans - The available vlans.
 * @param fabricId - A fabric id.
 * @returns Whether the VLAN is of type VLANDetails.
 */
export const getVLANsInFabric = (
  vlans: VLAN[],
  fabricId: Fabric["id"]
): VLAN[] => vlans.filter((vlan) => vlan.fabric === fabricId);

/**
 * @param vlans - The available vlans.
 * @param vlanId - A VLAN id.
 * @returns VLAN with a given id.
 */
export const getVlanById = (vlans: VLAN[], vlanId: VLAN["id"]): VLAN | null =>
  vlans.find((vlan) => vlan?.id === vlanId) || null;
