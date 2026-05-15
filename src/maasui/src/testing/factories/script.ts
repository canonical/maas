import { extend, random } from "cooky-cutter";

import { timestampedModel } from "./model";

import { ScriptType } from "@/app/store/script/types";
import type { Script } from "@/app/store/script/types";
import type { TimestampedModel } from "@/app/store/types/model";

export const script = extend<TimestampedModel, Script>(timestampedModel, {
  apply_configured_networking: false,
  default: false,
  description: "test description",
  destructive: false,
  for_hardware: () => [],
  hardware_type: random,
  may_reboot: false,
  name: (i: number) => `test name ${i}`,
  packages: () => ({}),
  parallel: random,
  parameters: () => ({}),
  recommission: false,
  results: () => ({}),
  script_type: ScriptType.COMMISSIONING,
  script: random,
  tags: () => [],
  timeout: "00:30:00",
  title: "commissioning script",
});
