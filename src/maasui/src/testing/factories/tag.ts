import { extend } from "cooky-cutter";

import { timestampedModel } from "./model";

import type { Tag } from "@/app/store/tag/types";
import type { TimestampedModel } from "@/app/store/types/model";

export const tag = extend<TimestampedModel, Tag>(timestampedModel, {
  comment: "test comment",
  controller_count: 0,
  definition: "",
  device_count: 0,
  kernel_opts: null,
  machine_count: 0,
  name: (i: number) => `test tag ${i}`,
});
