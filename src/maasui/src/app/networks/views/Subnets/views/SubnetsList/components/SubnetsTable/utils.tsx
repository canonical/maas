import type { SubnetsRowData } from "./useSubnetsTableColumns/useSubnetsTableColumns";

import { getVLANDisplay } from "@/app/store/vlan/utils";

export const filterSubnetsBySearchText = (
  data: SubnetsRowData[],
  searchText: string
) => {
  if (searchText.length === 0) {
    return data;
  } else {
    return data.filter(
      (subnet) =>
        subnet.name.includes(searchText) ||
        (subnet.vlan && getVLANDisplay(subnet.vlan)!.includes(searchText)) ||
        (subnet.fabric?.name && subnet.fabric.name.includes(searchText)) ||
        (subnet.space?.name && subnet.space.name.includes(searchText))
    );
  }
};
