import type { ScriptType } from "./enum";

import type { AnyObject, APIError } from "@/app/base/types";
import type { TimestampedModel } from "@/app/store/types/model";
import type { GenericState } from "@/app/store/types/state";

export type ScriptsPackages = Record<string, string[]>;

// Data from a Django JSONObjectField that could have any validly parsed JSON structure.
export type ScriptsParameters = AnyObject;

// Data from a Django JSONObjectField that could have any validly parsed JSON structure.
export type ScriptsResults = AnyObject;

export type Script = TimestampedModel & {
  apply_configured_networking: boolean;
  default: boolean;
  description: string;
  destructive: boolean;
  for_hardware: string[];
  hardware_type: number;
  may_reboot: boolean;
  name: string;
  packages: ScriptsPackages;
  parallel: number;
  parameters: ScriptsParameters;
  recommission: boolean;
  results: ScriptsResults;
  script_type: ScriptType;
  script: number;
  tags: string[];
  timeout: string;
  title: string;
};

export type ScriptState = GenericState<Script, APIError>;
