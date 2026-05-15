import type { StaticRoute } from "./base";
import type { StaticRouteMeta } from "./enum";

export type CreateParams = {
  destination: StaticRoute["destination"];
  gateway_ip: StaticRoute["gateway_ip"];
  metric?: StaticRoute["metric"];
  source: StaticRoute["source"];
};

export type UpdateParams = Partial<CreateParams> & {
  [StaticRouteMeta.PK]: StaticRoute[StaticRouteMeta.PK];
};
