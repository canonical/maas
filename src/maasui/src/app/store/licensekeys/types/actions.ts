import type { LicenseKeys } from "./base";
import type { LicenseKeysMeta } from "./enum";

export type CreateParams = {
  distro_series: LicenseKeys["distro_series"];
  license_key?: LicenseKeys["license_key"];
  osystem: LicenseKeys["osystem"];
};

export type UpdateParams = CreateParams & {
  [LicenseKeysMeta.PK]: LicenseKeys[LicenseKeysMeta.PK];
};
