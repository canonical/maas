import type { BondFormValues } from "./types";

import type { Selected } from "@/app/base/components/node/networking/types";
import type { Machine, MachineDetails } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";
import {
  getInterfaceById,
  getInterfaceName,
  getLinkFromNic,
  isBondOrBridgeParent,
} from "@/app/store/utils";
import type { VLAN } from "@/app/store/vlan/types";
import { preparePayload } from "@/app/utils";

export const getFirstSelected = (
  machine: Machine,
  selected: Selected[]
): Selected => {
  if (!isMachineDetails(machine)) {
    return selected[0];
  }
  const [firstSelected] = selected.sort((selectedA, selectedB) => {
    const nicA = getInterfaceById(machine, selectedA.nicId, selectedA.linkId);
    const linkA = getLinkFromNic(nicA, selectedA.linkId);
    const nicB = getInterfaceById(machine, selectedB.nicId, selectedB.linkId);
    const linkB = getLinkFromNic(nicB, selectedB.linkId);
    const nameA = getInterfaceName(machine, nicA, linkA);
    const nameB = getInterfaceName(machine, nicB, linkB);
    if (nameA < nameB) {
      return -1;
    }
    if (nameA > nameB) {
      return 1;
    }
    return 0;
  });
  return firstSelected;
};

/*
 * Find other nics that could be in this bond. They need to be physical
 * interfaces on the same vlan that are not already in a bond or bridge.
 */
export const getValidNics = (
  machine: MachineDetails,
  vlanId?: VLAN["id"] | null,
  child?: NetworkInterface | null
): NetworkInterface[] =>
  machine.interfaces.filter((nic) => {
    const hasSameVLAN = nic.vlan_id === vlanId;
    const isPhysical = nic.type === NetworkInterfaceTypes.PHYSICAL;
    const isABondOrBridgeParent = isBondOrBridgeParent(machine, nic);
    const isInBondOrBridge =
      isABondOrBridgeParent && !!child && nic.children.includes(child.id);
    return (
      hasSameVLAN && isPhysical && (!isABondOrBridgeParent || isInBondOrBridge)
    );
  });

type BondFormPayload = BondFormValues & {
  interface_id?: NetworkInterface["id"];
  link_id?: NetworkLink["id"];
  parents: NetworkInterface["parents"];
  system_id: Machine["system_id"];
};

/**
 * Fetch all the interface ids from the selected nics.
 */
export const getParentIds = (selected: Selected[]): NetworkInterface["id"][] =>
  selected.reduce<NetworkInterface["id"][]>((ids, { nicId }) => {
    if (nicId || nicId === 0) {
      ids.push(nicId);
    }
    return ids;
  }, []);

/**
 * Clean up the form values before dispatching.
 */
export const prepareBondPayload = (
  values: BondFormValues,
  selected: Selected[],
  systemId: Machine["system_id"],
  nic?: NetworkInterface | null,
  link?: NetworkLink | null
): BondFormPayload => {
  const parents = getParentIds(selected);
  const payload: BondFormPayload = {
    ...values,
    interface_id: nic?.id,
    link_id: link?.id,
    parents,
    system_id: systemId,
  };
  return preparePayload(payload, [], ["linkMonitoring", "macSource", "macNic"]);
};
