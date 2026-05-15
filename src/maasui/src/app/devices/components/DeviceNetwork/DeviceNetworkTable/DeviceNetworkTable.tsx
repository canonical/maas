import { GenericTable } from "@canonical/maas-react-components";
import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import type { DeviceNetworkRowData } from "./useDeviceNetworkTableColumns/useDeviceNetworkTableColumns";
import useDeviceNetworkTableColumns from "./useDeviceNetworkTableColumns/useDeviceNetworkTableColumns";

import { useFetchActions, useIsAllNetworkingDisabled } from "@/app/base/hooks";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device, DeviceMeta } from "@/app/store/device/types";
import { isDeviceDetails } from "@/app/store/device/utils";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { Fabric } from "@/app/store/fabric/types";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";
import type { NetworkInterface } from "@/app/store/types/node";
import {
  getInterfaceIPAddress,
  getInterfaceSubnet,
  getLinkInterface,
  getLinkModeDisplay,
} from "@/app/store/utils";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN } from "@/app/store/vlan/types";

type Props = {
  systemId: Device[DeviceMeta.PK];
};

const generateRowData = ({
  device,
  fabrics,
  vlans,
  subnets,
  isAllNetworkingDisabled,
}: {
  device: Device;
  fabrics: Fabric[];
  vlans: VLAN[];
  subnets: Subnet[];
  isAllNetworkingDisabled: boolean;
}) => {
  if (!isDeviceDetails(device)) return [];

  const rows: DeviceNetworkRowData[] = [];

  device.interfaces.forEach((nic: NetworkInterface) => {
    if (nic.links.length > 0) {
      nic.links.forEach((link) => {
        const [linkNic] = getLinkInterface(device, link);
        const subnet = getInterfaceSubnet(
          device,
          subnets,
          fabrics,
          vlans,
          isAllNetworkingDisabled,
          nic,
          link
        );
        rows.push({
          id: link.id,
          nic: linkNic,
          mac_address: linkNic?.mac_address,
          link,
          ip_address: getInterfaceIPAddress(device, fabrics, vlans, nic, link),
          ip_mode: getLinkModeDisplay(link),
          subnet,
          device,
        });
      });
    } else {
      const subnet = getInterfaceSubnet(
        device,
        subnets,
        fabrics,
        vlans,
        isAllNetworkingDisabled,
        nic
      );
      rows.push({
        id: nic.id,
        mac_address: nic.mac_address,
        nic,
        ip_address: getInterfaceIPAddress(device, fabrics, vlans, nic),
        ip_mode: getLinkModeDisplay(null),
        subnet,
        device,
      });
    }
  });

  return rows;
};

const DeviceNetworkTable = ({ systemId }: Props): React.ReactElement => {
  const device = useSelector((state: RootState) =>
    deviceSelectors.getById(state, systemId)
  );
  const loading = useSelector(deviceSelectors.loading);
  const fabrics = useSelector(fabricSelectors.all);
  const subnets = useSelector(subnetSelectors.all);
  const vlans = useSelector(vlanSelectors.all);
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(device);

  useFetchActions([
    fabricActions.fetch,
    subnetActions.fetch,
    vlanActions.fetch,
  ]);

  const columns = useDeviceNetworkTableColumns({
    isAllNetworkingDisabled,
    systemId,
  });

  if (!isDeviceDetails(device)) {
    return <Spinner text="Loading..." />;
  }

  const rowData = generateRowData({
    device,
    fabrics,
    vlans,
    subnets,
    isAllNetworkingDisabled,
  });

  return (
    <>
      <GenericTable
        aria-label="Interfaces"
        className="device-network-table"
        columns={columns}
        data={rowData}
        isLoading={loading && !device}
        noData="No interfaces available."
        sorting={[{ id: "mac_address", desc: true }]}
      />
    </>
  );
};

export default DeviceNetworkTable;
