import type {
  ScriptResultEstimated,
  ScriptResultMeta,
  ScriptResultNames,
  ScriptResultParamType,
  ScriptResultStatus,
  ScriptResultType,
} from "./enum";

import type { HardwareType } from "@/app/base/enum";
import type { APIError } from "@/app/base/types";
import type { Model, UtcDatetime } from "@/app/store/types/model";
import type { NetworkInterface } from "@/app/store/types/node";
import type { GenericState } from "@/app/store/types/state";

export type ScriptResultResult = {
  name: string;
  title: string;
  description: string;
  value: string;
  surfaced: boolean;
};

export type PartialScriptResult = Model & {
  endtime: number;
  estimated_runtime: ScriptResultEstimated | string;
  runtime: string;
  starttime?: number;
  status: ScriptResultStatus;
  status_name: string;
  suppressed: boolean;
  updated?: UtcDatetime;
};

export type ScriptResult = PartialScriptResult & {
  ended?: string;
  exit_status?: number | null;
  hardware_type: HardwareType;
  interface?: NetworkInterface | null;
  name: ScriptResultNames | string;
  parameters?: {
    interface?: {
      type: ScriptResultParamType.INTERFACE;
      value: Model & {
        name: string;
        mac_address: string;
        vendor: string;
        product?: string | null;
      };
      argument_format?: string;
    };
    runtime?: {
      type: ScriptResultParamType.RUNTIME;
      value: number;
      argument_format?: string;
    };
    storage?: {
      type: ScriptResultParamType.STORAGE;
      value?: Model & {
        id_path: string | null;
        model?: string;
        name: string;
        physical_blockdevice_id: number;
        serial?: string;
      };
      argument_format?: string;
    };
    url?: {
      type: ScriptResultParamType.URL;
      value: string;
      argument_format?: string;
    };
  };
  physical_blockdevice?: number | null;
  result_type: ScriptResultType;
  results: ScriptResultResult[];
  script?: number;
  script_version?: number | null;
  started?: UtcDatetime;
  tags: string;
};

export type ScriptResultHistory = Record<number, PartialScriptResult[]>;

export type ScriptResultData = {
  combined?: string;
  stdout?: string;
  stderr?: string;
  result?: string;
};

export type ScriptResultState = GenericState<ScriptResult, APIError> & {
  history: Record<ScriptResult[ScriptResultMeta.PK], PartialScriptResult[]>;
  logs: Record<ScriptResult[ScriptResultMeta.PK], ScriptResultData> | null;
};
