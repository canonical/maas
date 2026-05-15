import type { APIError } from "@/app/base/types";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import type { TimestampedModel } from "@/app/store/types/model";
import type { GenericState } from "@/app/store/types/state";

export type StaticRoute = TimestampedModel & {
  destination: Subnet[SubnetMeta.PK];
  gateway_ip: string;
  metric: number;
  source: Subnet[SubnetMeta.PK];
};

export type StaticRouteState = GenericState<StaticRoute, APIError>;
