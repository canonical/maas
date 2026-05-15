import type { SpaceMeta } from "./enum";

import type { APIError } from "@/app/base/types";
import type { TimestampedModel } from "@/app/store/types/model";
import type { GenericState } from "@/app/store/types/state";

export type Space = TimestampedModel & {
  description: string;
  name: string;
  subnet_ids: number[];
  vlan_ids: number[];
};

export type SpaceState = GenericState<Space, APIError> & {
  active: Space[SpaceMeta.PK] | null;
};
