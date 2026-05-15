import { useEffect, useState } from "react";

import { useDispatch, useSelector } from "react-redux";

import type { GroupByKey } from "./types";
import type { SubnetsRowData } from "./useSubnetsTableColumns/useSubnetsTableColumns";
import { filterSubnetsBySearchText } from "./utils";

import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { Fabric } from "@/app/store/fabric/types";
import { spaceActions } from "@/app/store/space";
import spaceSelectors from "@/app/store/space/selectors";
import type { Space } from "@/app/store/space/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN } from "@/app/store/vlan/types";
import { getDHCPStatus } from "@/app/store/vlan/utils";
import { simpleSortByKey } from "@/app/utils";

type UseSubnetsTable = {
  data: SubnetsRowData[];
  loaded: boolean;
};

export const useSubnetsTable = (
  groupBy: GroupByKey = "fabric"
): UseSubnetsTable => {
  const dispatch = useDispatch();
  const fabrics = useSelector(fabricSelectors.all);
  const fabricsLoaded = useSelector(fabricSelectors.loaded);
  const vlans = useSelector(vlanSelectors.all);
  const vlansLoaded = useSelector(vlanSelectors.loaded);
  const subnetsLoaded = useSelector(subnetSelectors.loaded);
  const subnets = useSelector(subnetSelectors.all);
  const spaces = useSelector(spaceSelectors.all);
  const spacesLoaded = useSelector(spaceSelectors.loaded);
  const loaded = fabricsLoaded && vlansLoaded && subnetsLoaded && spacesLoaded;

  const [state, setState] = useState<UseSubnetsTable>({
    data: [],
    loaded: false,
  });

  useEffect(() => {
    if (!fabricsLoaded) dispatch(fabricActions.fetch());
    if (!vlansLoaded) dispatch(vlanActions.fetch());
    if (!subnetsLoaded) dispatch(subnetActions.fetch());
    if (!spacesLoaded) dispatch(spaceActions.fetch());
  }, [dispatch, fabricsLoaded, vlansLoaded, subnetsLoaded, spacesLoaded]);

  useEffect(() => {
    if (loaded) {
      setState({
        data: generateTableData({
          fabrics,
          vlans,
          subnets,
          spaces,
          groupBy,
        }),
        loaded: true,
      });
    }
  }, [loaded, fabrics, vlans, subnets, spaces, groupBy]);

  return state;
};

const generateTableData = ({
  subnets,
  vlans,
  fabrics,
  spaces,
  groupBy,
}: {
  subnets: Subnet[];
  vlans: VLAN[];
  fabrics: Fabric[];
  spaces: Space[];
  groupBy: GroupByKey;
}): SubnetsRowData[] => {
  return subnets
    .map((subnet) => {
      const vlan = vlans.find((vlan) => vlan.id === subnet.vlan);
      const fabric = fabrics.find((fabric) => fabric.id === vlan?.fabric);
      const space = spaces.find((space) => space.id === subnet.space);
      return {
        id: subnet.id,
        cidr: subnet.cidr,
        name: subnet.name,
        vlan,
        dhcpStatus: getDHCPStatus(vlan, vlans, fabrics, true),
        fabric,
        space,
        available_string: subnet.statistics.available_string,
        groupId:
          groupBy === "fabric"
            ? fabric!.id.toString()
            : (space?.id ?? 0).toString(),
      };
    })
    .sort((a, b) => {
      if (groupBy === "fabric") {
        return a.fabric!.id - b.fabric!.id;
      } else if (a.space && b.space) {
        return simpleSortByKey<Partial<Space>, keyof Space>("name")(a, b);
      } else if (a.space && !b.space) {
        return -1;
      } else if (!a.space && b.space) {
        return 1;
      } else {
        return 0;
      }
    });
};

export const useSubnetsTableSearch = (
  subnetsTable: UseSubnetsTable,
  searchText: string
): UseSubnetsTable => {
  const [state, setState] = useState<UseSubnetsTable>({
    data: [],
    loaded: false,
  });

  useEffect(() => {
    if (subnetsTable.loaded) {
      setState({
        data: filterSubnetsBySearchText(subnetsTable.data, searchText),
        loaded: true,
      });
    }
  }, [subnetsTable, searchText]);

  return state;
};
