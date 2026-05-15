import type { PackageRepository } from "./base";
import type { PackageRepositoryMeta } from "./enum";

export type CreateParams = {
  arches?: PackageRepository["arches"];
  components?: PackageRepository["components"];
  disable_sources?: PackageRepository["disable_sources"];
  disabled_components?: PackageRepository["disabled_components"];
  disabled_pockets?: PackageRepository["disabled_pockets"];
  distributions?: PackageRepository["distributions"];
  enabled?: PackageRepository["enabled"];
  key?: PackageRepository["key"];
  name: PackageRepository["name"];
  url: PackageRepository["url"];
};

export type UpdateParams = CreateParams & {
  [PackageRepositoryMeta.PK]: PackageRepository[PackageRepositoryMeta.PK];
};
