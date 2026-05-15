import { useEffect } from "react";

import { useDispatch, useSelector } from "react-redux";
import { Navigate, Route, Routes } from "react-router";

import ModelNotFound from "@/app/base/components/ModelNotFound";
import PageContent from "@/app/base/components/PageContent";
import { useGetURLId } from "@/app/base/hooks/urls";
import urls from "@/app/base/urls";
import {
  DeviceConfiguration,
  DeviceDetailsHeader,
  DeviceNetwork,
  DeviceSummary,
} from "@/app/devices/components";
import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import { DeviceMeta } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import { isId, getRelativeRoute } from "@/app/utils";

const DeviceDetails = (): React.ReactElement => {
  const dispatch = useDispatch();
  const id = useGetURLId(DeviceMeta.PK);
  const device = useSelector((state: RootState) =>
    deviceSelectors.getById(state, id)
  );
  const devicesLoading = useSelector(deviceSelectors.loading);

  useEffect(() => {
    if (isId(id)) {
      // Set active device on load to ensure all device details are sent through
      // the websocket.
      dispatch(deviceActions.get(id));
      dispatch(deviceActions.setActive(id));
      dispatch(tagActions.fetch());
    }
    // Unset active device and cleanup state on unmount.
    return () => {
      dispatch(deviceActions.setActive(null));
      dispatch(deviceActions.cleanup());
    };
  }, [dispatch, id]);

  if (!isId(id) || (!devicesLoading && !device)) {
    return (
      <ModelNotFound id={id} linkURL={urls.devices.index} modelName="device" />
    );
  }

  const base = urls.devices.device.index(null);
  return device ? (
    <Routes>
      <Route
        element={
          <PageContent header={<DeviceDetailsHeader systemId={id} />}>
            <DeviceSummary systemId={id} />
          </PageContent>
        }
        path={getRelativeRoute(urls.devices.device.summary(null), base)}
      />
      <Route
        element={
          <PageContent header={<DeviceDetailsHeader systemId={id} />}>
            <DeviceNetwork systemId={id} />
          </PageContent>
        }
        path={getRelativeRoute(urls.devices.device.network(null), base)}
      />
      <Route
        element={
          <PageContent header={<DeviceDetailsHeader systemId={id} />}>
            <DeviceConfiguration systemId={id} />
          </PageContent>
        }
        path={getRelativeRoute(urls.devices.device.configuration(null), base)}
      />
      <Route
        element={<Navigate replace to={urls.devices.device.summary({ id })} />}
        path="/"
      />
    </Routes>
  ) : (
    <></>
  );
};

export default DeviceDetails;
