import { GenericTable } from "@canonical/maas-react-components";
import { useSelector } from "react-redux";

import { useNetworkCardTableColumns } from "./useNetworkCardTableColumns/useNetworkCardTableColumns";

import { useIsAllNetworkingDisabled } from "@/app/base/hooks";
import type { Device } from "@/app/store/device/types";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { MachineDetails } from "@/app/store/machine/types";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { NetworkInterface } from "@/app/store/types/node";
import vlanSelectors from "@/app/store/vlan/selectors";

type Props = {
  interfaces: NetworkInterface[];
  node: Device | MachineDetails;
};

const NetworkCardTable = ({ interfaces, node }: Props): React.ReactElement => {
  const fabrics = useSelector(fabricSelectors.all);
  const vlans = useSelector(vlanSelectors.all);
  const subnets = useSelector(subnetSelectors.all);
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(node);
  const data: NetworkInterface[] = interfaces.map((iface) => ({
    ...iface,
  }));

  const columns = useNetworkCardTableColumns({
    node,
    subnets,
    fabrics,
    vlans,
    isAllNetworkingDisabled,
  });

  return (
    <GenericTable
      className="network-card-table"
      columns={columns}
      data={data}
      isLoading={false}
      noData="No interfaces available."
      sorting={[{ id: "name", desc: false }]}
    />
  );
};

export default NetworkCardTable;
