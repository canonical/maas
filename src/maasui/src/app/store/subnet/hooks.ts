import { useSelector } from "react-redux";

import { reservedIpActions } from "../reservedip";

import { getHasIPAddresses } from "./utils";

import { useFetchActions } from "@/app/base/hooks";
import reservedIpSelectors from "@/app/store/reservedip/selectors";
import type { ReservedIp } from "@/app/store/reservedip/types";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";

/**
 * Get if DHCP is enabled on a given subnet
 * @param id - The id of the subnet to check.
 */
export const useIsDHCPEnabled = (
  id?: Subnet[SubnetMeta.PK] | null
): boolean => {
  const subnet = useSelector((state: RootState) =>
    subnetSelectors.getById(state, id)
  );
  const vlanOnSubnet = useSelector((state: RootState) =>
    vlanSelectors.getById(state, subnet?.vlan)
  );

  useFetchActions([vlanActions.fetch, subnetActions.fetch]);

  return vlanOnSubnet?.dhcp_on || false;
};

/**
 * Get if a subnet can be deleted.
 * @param id - The id of the subnet to check.
 */
export const useCanBeDeleted = (id?: Subnet[SubnetMeta.PK] | null): boolean => {
  const subnet = useSelector((state: RootState) =>
    subnetSelectors.getById(state, id)
  );
  const isDHCPEnabled = useIsDHCPEnabled(id);

  useFetchActions([subnetActions.fetch]);

  return !isDHCPEnabled || (isDHCPEnabled && !getHasIPAddresses(subnet));
};

export const useReservedIps = (
  subnetId: Subnet[SubnetMeta.PK]
): ReservedIp[] => {
  const reservedIps = useSelector((state: RootState) =>
    reservedIpSelectors.getBySubnet(state, subnetId)
  );

  useFetchActions([reservedIpActions.fetch]);

  return reservedIps;
};
