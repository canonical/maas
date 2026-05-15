import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import { useFetchActions } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device, DeviceMeta } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  systemId?: Device[DeviceMeta.PK] | null;
};

export enum Labels {
  LoadingDevices = "Loading devices",
}

const DeviceLink = ({ systemId }: Props): React.ReactElement | null => {
  const device = useSelector((state: RootState) =>
    deviceSelectors.getById(state, systemId)
  );
  const devicesLoading = useSelector(deviceSelectors.loading);

  useFetchActions([deviceActions.fetch]);

  if (devicesLoading) {
    return <Spinner aria-label={Labels.LoadingDevices} />;
  }
  if (!device) {
    return null;
  }
  return (
    <Link to={urls.devices.device.index({ id: device.system_id })}>
      <strong>{device.hostname}</strong>
      <span>.{device.domain.name}</span>
    </Link>
  );
};

export default DeviceLink;
