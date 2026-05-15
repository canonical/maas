import type { APIError } from "@/app/base/types";
import type { Model } from "@/app/store/types/model";
import type { GenericState } from "@/app/store/types/state";

export type LicenseKeys = Model & {
  distro_series: string;
  license_key: string;
  osystem: string;
  resource_uri: string;
};

export type LicenseKeysState = GenericState<LicenseKeys, APIError>;
