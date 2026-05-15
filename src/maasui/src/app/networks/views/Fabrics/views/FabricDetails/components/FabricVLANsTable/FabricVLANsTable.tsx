import { GenericTable } from "@canonical/maas-react-components";
import { useSelector } from "react-redux";

import type { FabricVLANsRowData } from "./useFabricVLANsTableColumns/useFabricVLANsTableColumns";
import useFabricVLANsTableColumns from "./useFabricVLANsTableColumns/useFabricVLANsTableColumns";

import TitledSection from "@/app/base/components/TitledSection";
import { useFetchActions } from "@/app/base/hooks";
import type { Fabric } from "@/app/store/fabric/types";
import type { RootState } from "@/app/store/root/types";
import { spaceActions } from "@/app/store/space";
import spaceSelectors from "@/app/store/space/selectors";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";
import { getSubnetsInVLAN } from "@/app/store/subnet/utils";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN } from "@/app/store/vlan/types";

const generateRows = (
  vlans: VLAN[],
  subnets: Subnet[]
): FabricVLANsRowData[] => {
  const rows: FabricVLANsRowData[] = [];

  vlans.forEach((vlan) => {
    const subnetsInVlan = getSubnetsInVLAN(subnets, vlan.id);
    const vlanHasSubnets = subnetsInVlan.length > 0;

    if (!vlanHasSubnets) {
      rows.push({
        id: vlan.id,
        vid: vlan.vid,
        spaceId: vlan.space,
        isChildRow: false,
      });
    } else {
      const newRow: FabricVLANsRowData = {
        id: vlan.id,
        vid: vlan.vid,
        spaceId: vlan.space,
        children: [],
        isChildRow: false,
      };
      subnetsInVlan.forEach((subnet, i) => {
        if (i === 0) {
          newRow.subnetId = subnet.id;
          newRow.subnetAvailableIps = subnet.statistics.available_string;
        } else {
          newRow.children?.push({
            id: vlan.id,
            vid: vlan.vid,
            isChildRow: true,
            subnetId: subnet.id,
            subnetAvailableIps: subnet.statistics.available_string,
          });
        }
      });
      rows.push(newRow);
    }
  });
  return rows;
};

const FabricVLANsTable = ({
  fabric,
}: {
  fabric: Fabric;
}): React.ReactElement => {
  const vlans = useSelector((state: RootState) =>
    vlanSelectors.getByFabric(state, fabric.id)
  );
  const spacesLoading = useSelector(spaceSelectors.loading);
  const subnets = useSelector(subnetSelectors.all);
  const subnetsLoading = useSelector(subnetSelectors.loading);
  const vlansLoading = useSelector(vlanSelectors.loading);
  const loading = spacesLoading || subnetsLoading || vlansLoading;

  useFetchActions([spaceActions.fetch, subnetActions.fetch, vlanActions.fetch]);

  const columns = useFabricVLANsTableColumns();
  const rowData = generateRows(vlans, subnets);

  return (
    <TitledSection title="VLANs on this fabric">
      <GenericTable<FabricVLANsRowData>
        className="fabric-vlans"
        columns={columns}
        data={rowData}
        getSubRows={(originalRow) => originalRow.children}
        isLoading={loading}
        noData="No VLANs on this fabric."
        sorting={[
          { id: "vid", desc: false },
          { id: "subnetAvailableIps", desc: false },
        ]}
      />
    </TitledSection>
  );
};

export default FabricVLANsTable;
