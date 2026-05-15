import type { VLANMeta, VlanVid } from "./enum";

import type { APIError } from "@/app/base/types";
import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import type { Fabric, FabricMeta } from "@/app/store/fabric/types";
import type { Space, SpaceMeta } from "@/app/store/space/types";
import type { Subnet } from "@/app/store/subnet/types";
import type { TimestampedModel } from "@/app/store/types/model";
import type { Node } from "@/app/store/types/node";
import type { EventError, GenericState } from "@/app/store/types/state";

export type BaseVLAN = TimestampedModel & {
  description: string;
  dhcp_on: boolean;
  external_dhcp: string | null;
  fabric: Fabric[FabricMeta.PK];
  mtu: number;
  name: string;
  primary_rack: Controller[ControllerMeta.PK] | null;
  rack_sids: Controller[ControllerMeta.PK][];
  relay_vlan: VLAN[VLANMeta.PK] | null;
  secondary_rack: Controller[ControllerMeta.PK] | null;
  space: Space[SpaceMeta.PK] | null;
  subnet_ids: Subnet["id"][];
  vid: VlanVid.UNTAGGED | number;
};

export type VLANDetails = BaseVLAN & {
  node_ids: Node["id"][];
  space_ids: Space[SpaceMeta.PK][];
};

export type VLAN = BaseVLAN | VLANDetails;

export type VLANStatus = {
  configuringDHCP: boolean;
};

export type VLANStatuses = Record<string, VLANStatus>;

export type VLANState = GenericState<VLAN, APIError> & {
  active: VLAN[VLANMeta.PK] | null;
  eventErrors: EventError<VLAN, APIError, VLANMeta.PK>[];
  statuses: VLANStatuses;
};
