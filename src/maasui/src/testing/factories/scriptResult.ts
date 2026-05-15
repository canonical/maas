import { array, define, extend } from "cooky-cutter";

import { timestamp } from "./general";
import { model } from "./model";

import type {
  PartialScriptResult,
  ScriptResult,
  ScriptResultData,
  ScriptResultResult,
} from "@/app/store/scriptresult/types";
import type { Model } from "@/app/store/types/model";

export const scriptResultResult = define<ScriptResultResult>({
  name: (i: number) => `test result ${i}`,
  title: (i: number) => `test result ${i} title`,
  description: "test description",
  value: "test value",
  surfaced: false,
});

export const partialScriptResult = extend<Model, PartialScriptResult>(model, {
  endtime: 1605243027.158285,
  estimated_runtime: "test runtime",
  runtime: "0:00:00",
  starttime: 605243026.966467,
  status: 2,
  status_name: "test status",
  suppressed: false,
  updated: () => timestamp("Fri, 13 Nov. 2020 04:50:27"),
});

export const scriptResult = extend<Model, ScriptResult>(model, {
  ended: "Fri, 13 Nov. 2020 04:50:27",
  endtime: 1605243027.158285,
  estimated_runtime: "test runtime",
  exit_status: 0,
  hardware_type: 3,
  interface: null,
  name: (i: number) => `test scriptResult ${i}`,
  parameters: () => ({}),
  physical_blockdevice: 2451,
  result_type: 1,
  results: array(scriptResultResult),
  runtime: "0:00:00",
  script: 1,
  script_version: 2,
  started: () => timestamp("Fri, 13 Nov. 2020 04:50:26"),
  starttime: 605243026.966467,
  status: 2,
  status_name: "test status",
  suppressed: false,
  tags: "test, tags",
  updated: () => timestamp("Fri, 13 Nov. 2020 04:50:27"),
});

export const scriptResultData = define<ScriptResultData>({
  combined: "combined content",
  stdout: "stdout content",
  stderr: "",
  result: "yaml result",
});
