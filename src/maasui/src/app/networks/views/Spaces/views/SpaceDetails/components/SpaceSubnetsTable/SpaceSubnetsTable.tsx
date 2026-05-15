import type { ReactElement } from "react";
import { useEffect, useMemo } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { useDispatch, useSelector } from "react-redux";

import useSpaceSubnetsTableColumns from "./useSpaceSubnetsTableColumns/useSpaceSubnetsTableColumns";

import TitledSection from "@/app/base/components/TitledSection";
import type { RootState } from "@/app/store/root/types";
import type { Space } from "@/app/store/space/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN } from "@/app/store/vlan/types";
import { getVlanById } from "@/app/store/vlan/utils";
import { simpleSortByKey } from "@/app/utils";

import "./_index.scss";

export type SpaceSubnet = {
  id: number;
  available_ips: number;
  vlan: number;
  fabric?: number;
};

const getSpaceSubnets = (subnets: Subnet[], vlans: VLAN[]): SpaceSubnet[] => {
  return subnets.sort(simpleSortByKey("cidr")).map((subnet: Subnet) => ({
    id: subnet.id,
    available_ips: Number.parseInt(
      subnet.statistics.available_string.slice(0, -1)
    ),
    vlan: subnet.vlan,
    fabric: getVlanById(vlans, subnet.vlan)?.fabric,
  }));
};

const SpaceSubnetsTable = ({ space }: { space: Space }): ReactElement => {
  const vlans = useSelector(vlanSelectors.all);
  const subnets = useSelector((state: RootState) =>
    subnetSelectors.getBySpace(state, space.id)
  );
  const dispatch = useDispatch();
  const vlansLoading = useSelector(vlanSelectors.loading);
  const subnetsLoading = useSelector(subnetSelectors.loading);
  const vlansLoaded = useSelector(vlanSelectors.loaded);
  const subnetsLoaded = useSelector(subnetSelectors.loaded);

  useEffect(() => {
    if (!subnetsLoaded) dispatch(subnetActions.fetch());
    if (!vlansLoaded) dispatch(vlanActions.fetch());
  }, [dispatch, subnetsLoaded, vlansLoaded]);

  const columns = useSpaceSubnetsTableColumns();
  const data = useMemo(() => getSpaceSubnets(subnets, vlans), [subnets, vlans]);

  return (
    <TitledSection title="Subnets on this space">
      <GenericTable
        columns={columns}
        data={data}
        isLoading={vlansLoading || subnetsLoading}
        noData="There are no subnets on this space."
        sorting={[{ id: "id", desc: true }]}
      />
    </TitledSection>
  );
};

export default SpaceSubnetsTable;
