import type { APIError } from "@/app/base/types";
import type { TimestampedModel } from "@/app/store/types/model";
import type { GenericState } from "@/app/store/types/state";

export type PackageRepository = TimestampedModel & {
  arches: string[];
  components: string[];
  default: boolean;
  disable_sources: boolean;
  disabled_components: string[];
  disabled_pockets: string[];
  distributions: string[];
  enabled: boolean;
  key: string;
  name: string;
  url: string;
};

export type PackageRepositoryState = GenericState<PackageRepository, APIError>;
