import { Spinner, Strip } from "@canonical/react-components";
import { useSelector } from "react-redux";

import DeviceOverviewCard from "./DeviceOverviewCard";

import NodeSummaryNetworkCard from "@/app/base/components/NodeSummaryNetworkCard";
import { useWindowTitle } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device, DeviceMeta } from "@/app/store/device/types";
import { isDeviceDetails } from "@/app/store/device/utils";
import type { RootState } from "@/app/store/root/types";

export enum Label {
  Title = "Device summary",
}

type Props = {
  systemId: Device[DeviceMeta.PK];
};

const DeviceSummary = ({ systemId }: Props): React.ReactElement => {
  const device = useSelector((state: RootState) =>
    deviceSelectors.getById(state, systemId)
  );
  useWindowTitle(`${`${device?.hostname}` || "Device"} summary`);

  if (!device) {
    return (
      <Strip data-testid="loading-device" shallow>
        <Spinner text="Loading..." />
      </Strip>
    );
  }
  return (
    <Strip aria-label={Label.Title} data-testid="device-summary" shallow>
      <div className="device-summary">
        <div className="device-summary__overview">
          <DeviceOverviewCard systemId={systemId} />
        </div>
        <div className="device-summary__network">
          <NodeSummaryNetworkCard
            interfaces={isDeviceDetails(device) ? device.interfaces : null}
            networkURL={urls.devices.device.network({ id: systemId })}
            node={device}
          />
        </div>
      </div>
    </Strip>
  );
};

export default DeviceSummary;
