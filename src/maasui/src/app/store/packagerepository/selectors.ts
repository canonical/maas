import { getRepoDisplayName } from "./utils";

import { PackageRepositoryMeta } from "@/app/store/packagerepository/types";
import type {
  PackageRepository,
  PackageRepositoryState,
} from "@/app/store/packagerepository/types";
import type { RootState } from "@/app/store/root/types";
import { generateBaseSelectors } from "@/app/store/utils";

const searchFunction = (repo: PackageRepository, term: string) =>
  getRepoDisplayName(repo.name).includes(term) ||
  repo.name.includes(term) ||
  repo.url.includes(term);

const defaultSelectors = generateBaseSelectors<
  PackageRepositoryState,
  PackageRepository,
  PackageRepositoryMeta.PK
>(PackageRepositoryMeta.MODEL, PackageRepositoryMeta.PK, searchFunction);

/**
 * Returns the main archive package repository.
 * @param state - The redux state.
 * @returns The main archive package repository.
 */
const mainArchive = (state: RootState): PackageRepository | null =>
  state.packagerepository.items.find(
    (repo) => repo.default && repo.name === "main_archive"
  ) || null;

/**
 * Returns the ports archive package repository.
 * @param state - The redux state.
 * @returns The ports archive package repository.
 */
const portsArchive = (state: RootState): PackageRepository | null =>
  state.packagerepository.items.find(
    (repo) => repo.default && repo.name === "ports_archive"
  ) || null;

const selectors = { ...defaultSelectors, portsArchive, mainArchive };

export default selectors;
