import type {
  ComponentsToDisableEnum,
  KnownArchesEnum,
  PackageRepositoryResponse,
  PocketsToDisableEnum,
} from "@/app/apiclient";

export type RepositoryType = "ppa" | "repository";

export type RepositoryFormValues = {
  arches: KnownArchesEnum[];
  components: string;
  default: boolean;
  disable_sources: PackageRepositoryResponse["disable_sources"];
  disabled_components: ComponentsToDisableEnum[];
  disabled_pockets: PocketsToDisableEnum[];
  distributions: string;
  enabled: PackageRepositoryResponse["enabled"];
  key: PackageRepositoryResponse["key"];
  name: PackageRepositoryResponse["name"];
  url: PackageRepositoryResponse["url"];
};
