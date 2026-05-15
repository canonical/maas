import { useEffect, useState } from "react";

import { useDispatch, useSelector } from "react-redux";

import type { ControllerTableData } from "./types";

import controllerSelectors from "@/app/store/controller/selectors";
import type {
  Controller,
  ControllerDetails,
  ControllerMeta,
} from "@/app/store/controller/types";
import { isControllerDetails } from "@/app/store/controller/utils";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { Fabric } from "@/app/store/fabric/types";
import { getFabricById } from "@/app/store/fabric/utils";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";
import { getSubnetsInVLAN } from "@/app/store/subnet/utils";
import { getBondOrBridgeChild } from "@/app/store/utils/node/networking";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN } from "@/app/store/vlan/types";
import {
  getDHCPStatus,
  getVlanById,
  getVLANDisplay,
} from "@/app/store/vlan/utils";
import { simpleSortByKey } from "@/app/utils";

const getTableData = (
  data: {
    fabrics: Fabric[];
    vlans: VLAN[];
    subnets: Subnet[];
  },
  controller: ControllerDetails
): ControllerTableData[] => {
  const rows: ControllerTableData[] = controller.interfaces.reduce<
    ControllerTableData[]
  >((rows, nic) => {
    const rowExists = rows.some((row) => row.vlan?.id === nic.vlan_id);
    const hasBondOrBridgeChild = !!getBondOrBridgeChild(controller, nic);
    const controllerVlan = getVlanById(data.vlans, nic.vlan_id);

    if (!rowExists && !hasBondOrBridgeChild && controllerVlan) {
      const controllerFabric = getFabricById(
        data.fabrics,
        controllerVlan.fabric
      );
      rows.push({
        fabric: controllerFabric,
        vlan: controllerVlan,
        dhcp: getDHCPStatus(controllerVlan, data.vlans, data.fabrics),
        subnet: getSubnetsInVLAN(data.subnets, nic.vlan_id),
        sortKey: controllerFabric
          ? controllerFabric.name + "|" + getVLANDisplay(controllerVlan)
          : undefined,
        primary_rack: controllerVlan?.primary_rack
          ? controllerVlan.primary_rack
          : null,
        secondary_rack: controllerVlan?.secondary_rack
          ? controllerVlan.secondary_rack
          : null,
      });
    }
    return rows;
  }, []);

  return rows.sort(
    simpleSortByKey("sortKey", {
      alphanumeric: true,
    })
  );
};

export const useControllerVLANsTable = ({
  systemId,
}: {
  systemId: Controller[ControllerMeta.PK];
}): { data: ControllerTableData[]; loaded: boolean } => {
  const dispatch = useDispatch();
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, systemId)
  );
  const fabrics = useSelector(fabricSelectors.all);
  const fabricsLoaded = useSelector(fabricSelectors.loaded);
  const vlans = useSelector(vlanSelectors.all);
  const vlansLoaded = useSelector(vlanSelectors.loaded);
  const subnetsLoaded = useSelector(subnetSelectors.loaded);
  const subnets = useSelector(subnetSelectors.all);
  const loaded = fabricsLoaded && vlansLoaded && subnetsLoaded;

  const [state, setState] = useState<{
    data: ControllerTableData[];
    loaded: boolean;
  }>({
    data: [],
    loaded: false,
  });

  useEffect(() => {
    if (!fabricsLoaded) dispatch(fabricActions.fetch());
    if (!vlansLoaded) dispatch(vlanActions.fetch());
    if (!subnetsLoaded) dispatch(subnetActions.fetch());
  }, [dispatch, fabricsLoaded, vlansLoaded, subnetsLoaded]);

  useEffect(() => {
    if (isControllerDetails(controller) && loaded) {
      setState({
        data: getTableData({ fabrics, vlans, subnets }, controller),
        loaded: true,
      });
    }
  }, [loaded, fabrics, vlans, subnets, controller]);

  return state;
};
