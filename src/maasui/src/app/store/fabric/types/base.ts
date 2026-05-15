import type { FabricMeta } from "./enum";

import type { APIError } from "@/app/base/types";
import type { TimestampedModel } from "@/app/store/types/model";
import type { GenericState } from "@/app/store/types/state";

export type Fabric = TimestampedModel & {
  class_type: string | null;
  default_vlan_id: number;
  description: string;
  name: string;
  vlan_ids: number[];
};

export type FabricState = GenericState<Fabric, APIError> & {
  active: Fabric[FabricMeta.PK] | null;
};
