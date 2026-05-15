import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import DeviceNetworkTable from "./DeviceNetworkTable";

import DHCPTable from "@/app/base/components/DHCPTable";
import NetworkActionRow from "@/app/base/components/NetworkActionRow";
import NodeNetworkTab from "@/app/base/components/NodeNetworkTab";
import { useWindowTitle } from "@/app/base/hooks";
import deviceSelectors from "@/app/store/device/selectors";
import { DeviceMeta } from "@/app/store/device/types";
import type { Device } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";

export enum Label {
  Title = "Device network",
}

type Props = {
  systemId: Device[DeviceMeta.PK];
};

const DeviceNetwork = ({ systemId }: Props): React.ReactElement => {
  const device = useSelector((state: RootState) =>
    deviceSelectors.getById(state, systemId)
  );

  useWindowTitle(`${device?.fqdn ? `${device?.fqdn} ` : "Device"} network`);

  if (!device) {
    return <Spinner text="Loading..." />;
  }

  return (
    <>
      <NodeNetworkTab
        actions={() => <NetworkActionRow node={device} />}
        aria-label={Label.Title}
        dhcpTable={() => (
          <DHCPTable
            className="u-no-padding--top"
            modelName={DeviceMeta.MODEL}
            node={device}
          />
        )}
        interfaceTable={() => <DeviceNetworkTable systemId={systemId} />}
      />
    </>
  );
};

export default DeviceNetwork;
