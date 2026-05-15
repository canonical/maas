import { extend } from "cooky-cutter";

import { timestampedModel } from "./model";

import type { StaticRoute } from "@/app/store/staticroute/types";
import type { TimestampedModel } from "@/app/store/types/model";

export const staticRoute = extend<TimestampedModel, StaticRoute>(
  timestampedModel,
  {
    destination: 456,
    gateway_ip: "192.168.1.1",
    metric: 0,
    source: 123,
  }
);
