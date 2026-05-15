import { GenericTable } from "@canonical/maas-react-components";
import { useSelector } from "react-redux";

import useVLANSubnetsTableColumns from "./useVLANSubnetsTableColumns/useVLANSubnetsTableColumns";

import TitledSection from "@/app/base/components/TitledSection";
import type { RootState } from "@/app/store/root/types";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { VLAN, VLANMeta } from "@/app/store/vlan/types";

type Props = {
  id: VLAN[VLANMeta.PK] | null;
};

const VLANSubnetsTable = ({ id }: Props): React.ReactElement | null => {
  const subnets = useSelector((state: RootState) =>
    subnetSelectors.getByVLAN(state, id)
  );
  const subnetsLoading = useSelector(subnetSelectors.loading);
  const columns = useVLANSubnetsTableColumns();
  const data = subnets.map((subnet) => ({
    id: subnet.id,
    cidr: subnet.cidr,
    usage: subnet.statistics.usage,
    usage_string: subnet.statistics.usage_string,
    managed: subnet.managed,
    allow_proxy: subnet.allow_proxy,
    allow_dns: subnet.allow_dns,
  }));

  return (
    <TitledSection title="Subnets on this VLAN">
      <GenericTable
        className="vlan-subnets"
        columns={columns}
        data={data}
        isLoading={subnetsLoading}
        noData="There are no subnets on this VLAN"
        sorting={[{ id: "cidr", desc: false }]}
        variant="regular"
      />
    </TitledSection>
  );
};

export default VLANSubnetsTable;
