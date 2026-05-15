import { StaticRouteMeta } from "@/app/store/staticroute/types";
import type {
  StaticRoute,
  StaticRouteState,
} from "@/app/store/staticroute/types";
import { generateBaseSelectors } from "@/app/store/utils";

const selectors = generateBaseSelectors<
  StaticRouteState,
  StaticRoute,
  StaticRouteMeta.PK
>(StaticRouteMeta.MODEL, StaticRouteMeta.PK);

export default selectors;
