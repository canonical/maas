import { useSelector } from "react-redux";

import { useFetchActions } from "@/app/base/hooks";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Controller } from "@/app/store/controller/types";
import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device } from "@/app/store/device/types";
import type { DHCPSnippet } from "@/app/store/dhcpsnippet/types";
import { ipRangeActions } from "@/app/store/iprange";
import ipRangeSelectors from "@/app/store/iprange/selectors";
import type { Machine } from "@/app/store/machine/types";
import { useFetchMachine } from "@/app/store/machine/utils/hooks";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";

export const useDhcpTarget = (
  nodeId?: DHCPSnippet["node"],
  subnetId?: DHCPSnippet["subnet"],
  ipRangeId?: DHCPSnippet["iprange"]
): {
  loading: boolean;
  loaded: boolean;
  target: Controller | Device | Machine | Subnet | null;
  type: "controller" | "device" | "iprange" | "machine" | "subnet" | null;
} => {
  const iprange = useSelector((state: RootState) =>
    ipRangeSelectors.getById(state, ipRangeId)
  );
  const subnetLoading = useSelector(subnetSelectors.loading);
  const subnetLoaded = useSelector(subnetSelectors.loaded);
  const subnet = useSelector((state: RootState) =>
    subnetSelectors.getById(state, subnetId)
  );
  const controllerLoading = useSelector(controllerSelectors.loading);
  const controllerLoaded = useSelector(controllerSelectors.loaded);
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, nodeId)
  );
  const deviceLoading = useSelector(deviceSelectors.loading);
  const deviceLoaded = useSelector(deviceSelectors.loaded);
  const device = useSelector((state: RootState) =>
    deviceSelectors.getById(state, nodeId)
  );
  const {
    machine,
    loaded: machineLoaded = false,
    loading: machineLoading = false,
  } = useFetchMachine(nodeId);

  const isLoading =
    (!!subnetId && subnetLoading) ||
    (!!nodeId && (controllerLoading || deviceLoading || machineLoading));
  const hasLoaded =
    (!!subnetId && subnetLoaded) ||
    // The machine loaded state will only be true if a machine was found.
    (!!nodeId && ((controllerLoaded && deviceLoaded) || machineLoaded));

  useFetchActions([
    subnetActions.fetch,
    ipRangeActions.fetch,
    controllerActions.fetch,
    deviceActions.fetch,
  ]);

  return {
    loading: isLoading,
    loaded: hasLoaded,
    target: subnet || machine || device || controller,
    type:
      (iprange && "iprange") ||
      (subnet && "subnet") ||
      (controller && "controller") ||
      (device && "device") ||
      (machine && "machine") ||
      null,
  };
};
