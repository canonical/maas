import type { IPRangeType } from "./enum";

import type { APIError } from "@/app/base/types";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import type { TimestampedModel } from "@/app/store/types/model";
import type { GenericState } from "@/app/store/types/state";
import type { VLAN, VLANMeta } from "@/app/store/vlan/types";

export type IPRange = TimestampedModel & {
  comment: string;
  end_ip: string;
  start_ip: string;
  subnet: Subnet[SubnetMeta.PK] | null;
  type: IPRangeType;
  user: string;
  vlan: VLAN[VLANMeta.PK] | null;
};

export type IPRangeState = GenericState<IPRange, APIError>;
