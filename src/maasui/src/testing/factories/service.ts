import { extend } from "cooky-cutter";

import { model } from "./model";

import { ServiceName, ServiceStatus } from "@/app/store/service/types";
import type { Service } from "@/app/store/service/types";
import type { Model } from "@/app/store/types/model";

export const service = extend<Model, Service>(model, {
  name: ServiceName.PROXY_RACK,
  status: ServiceStatus.RUNNING,
  status_info: "test info",
});
