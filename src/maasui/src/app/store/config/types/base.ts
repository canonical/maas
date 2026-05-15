import type { ConfigNames } from "./enum";

import type { APIError } from "@/app/base/types";
import type { GenericState } from "@/app/store/types/state";

export type ConfigChoice = [number | string, string];

export type ConfigValues = boolean | number | string | null;

export type Config<V> = {
  name: ConfigNames;
  value: V;
  choices?: ConfigChoice[];
};

export type ConfigState = GenericState<Config<ConfigValues>, APIError>;
