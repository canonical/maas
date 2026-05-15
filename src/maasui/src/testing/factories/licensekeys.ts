import { extend } from "cooky-cutter";

import { model } from "./model";

import type { LicenseKeys } from "@/app/store/licensekeys/types";
import type { Model } from "@/app/store/types/model";

export const licenseKeys = extend<Model, LicenseKeys>(model, {
  distro_series: "win2012",
  license_key: "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX",
  osystem: "windows",
  resource_uri: "/MAAS/api/2.0/license-key/windows/win2012",
});
