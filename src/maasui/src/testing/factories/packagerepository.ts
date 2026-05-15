import { extend } from "cooky-cutter";

import { timestampedModel } from "./model";

import type { PackageRepository } from "@/app/store/packagerepository/types";
import type { TimestampedModel } from "@/app/store/types/model";

export const packageRepository = extend<TimestampedModel, PackageRepository>(
  timestampedModel,
  {
    name: (i: number) => `test-repo-${i}`,
    url: "test url",
    distributions: () => [],
    disabled_pockets: () => [],
    disabled_components: () => [],
    disable_sources: false,
    components: () => [],
    arches: () => [],
    key: "",
    default: false,
    enabled: false,
  }
);
