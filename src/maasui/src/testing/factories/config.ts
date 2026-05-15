import { define } from "cooky-cutter";

import type { Config, ConfigValues } from "@/app/store/config/types";
import { ConfigNames } from "@/app/store/config/types";

export const config = define<Config<ConfigValues>>({
  name: ConfigNames.MAAS_NAME,
  value: "maas",
});
