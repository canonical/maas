/**
 * Selector for os info.
 */
import { createSelector } from "@reduxjs/toolkit";
import { createCachedSelector } from "re-reselect";

import { generateGeneralSelector } from "./utils";

import type {
  OSInfoState,
  OSInfoOsKernelEntry,
  OSInfoOSystem,
  OSInfoRelease,
} from "@/app/store/general/types";
import type { RootState } from "@/app/store/root/types";

const generalSelectors = generateGeneralSelector<"osInfo">("osInfo");

export type OSInfoOption = {
  label: string;
  value: string;
};

export type OSInfoOptions = Record<string, OSInfoOption[]>;

/**
 * Returns kernels data.
 * @param {OSInfo} data - The osinfo data.
 * @param {String} release - The release to get kernel options for.
 * @returns {OSInfoOption[]} - The available kernel options.
 */
const _getUbuntuKernelOptions = (
  data: OSInfoState["data"],
  release: string
): OSInfoOption[] => {
  let kernelOptions: OSInfoOsKernelEntry[] = [];

  if (data?.kernels?.ubuntu?.[release]) {
    kernelOptions = data.kernels.ubuntu[release];
  }
  const noMin = ["", "No minimum kernel"];

  return [noMin, ...kernelOptions].map((option) => ({
    value: option[0],
    label: option[1],
  }));
};

/**
 * Returns kernels data.
 * @param {RootState} state -The redux state.
 * @param {String} release - The release to get kernel options for.
 * @returns {OSInfoOption[]} - The available kernel options.
 */
const getUbuntuKernelOptions = createSelector(
  [generalSelectors.get, (_state: RootState, release: string) => release],
  (allOsInfo, release) => _getUbuntuKernelOptions(allOsInfo, release)
);

/**
 * Returns all ubuntu kernel options
 * @param {RootState} state - the redux state
 * @returns {OSInfoOptions} - all ubuntu kernel options
 */
const getAllUbuntuKernelOptions = createSelector(
  [generalSelectors.get],
  (allOsInfo: OSInfoState["data"]) => {
    const allUbuntuKernelOptions: OSInfoOptions = {};

    if (allOsInfo?.kernels?.ubuntu) {
      Object.keys(allOsInfo.kernels.ubuntu).forEach((key) => {
        allUbuntuKernelOptions[key] = _getUbuntuKernelOptions(allOsInfo, key);
      });
    }

    return allUbuntuKernelOptions;
  }
);

/**
 * Returns OS releases
 * @param {OSInfo} data - The osinfo data.
 * @param {String} os - the OS to get releases of
 * @returns {OSInfoOption[]} - the available OS releases
 */
const _getOsReleases = (
  allOsInfo: OSInfoState["data"],
  os?: string
): OSInfoOption[] => {
  let osReleases: OSInfoOption[] = [];

  if (allOsInfo?.releases) {
    let releases = allOsInfo.releases;
    if (os) {
      releases = releases.filter((release: OSInfoRelease) =>
        release[0].includes(os)
      );
    }
    osReleases = releases.map((release: OSInfoRelease) => ({
      value: release[0].split("/")[1],
      label: release[1],
    }));
  }

  return osReleases;
};

/**
 * Returns OS releases
 * @param {RootState} state - the redux state
 * @param {String} os - the OS to get releases of
 * @returns {OSInfoOption[]} - the available OS releases
 */
const getOsReleases = createCachedSelector(
  generalSelectors.get,
  (_state: RootState, os: string | undefined) => os,
  (allOsInfo, os) => _getOsReleases(allOsInfo, os)
)((_state, os) => os || "");

/**
 * Returns an object with all OS releases
 * @param {RootState} state - the redux state
 * @returns {OSInfoOptions} - all OS releases
 */
const getAllOsReleases = createSelector(
  [generalSelectors.get],
  (allOsInfo: OSInfoState["data"]): OSInfoOptions => {
    const allOsReleases: OSInfoOptions = {};

    if (allOsInfo?.osystems && allOsInfo?.releases) {
      allOsInfo.osystems.forEach((osystem: OSInfoOSystem) => {
        const os = osystem[0];
        allOsReleases[os] = _getOsReleases(allOsInfo, os);
      });
    }

    return allOsReleases;
  }
);

/**
 * Returns an object with all licensed OS releases.
 * @param {RootState} state - the redux state
 * @returns {OSInfoOptions} - all OS releases
 *
 */
const getLicensedOsReleases = createSelector([getAllOsReleases], (releases) => {
  const results: OSInfoOptions = {};
  for (const [key, value] of Object.entries(releases)) {
    const licensedReleases = value.filter((release) => {
      return release.value.endsWith("*");
    });

    if (licensedReleases.length > 0) {
      const releases = licensedReleases.map((r) => {
        r.value = r.value.slice(0, -1);
        return r;
      });
      results[key] = releases;
    }
  }
  return results;
});

const getLicensedOsystems = createSelector(
  [getLicensedOsReleases],
  (releases) => {
    const osystems = Object.keys(releases);
    if (osystems) {
      return osystems.map((osystem) => [
        osystem,
        `${osystem.charAt(0).toUpperCase()}${osystem.slice(1)}`,
      ]);
    }
    return [];
  }
);

const osInfo = {
  ...generalSelectors,
  getUbuntuKernelOptions,
  getAllUbuntuKernelOptions,
  getOsReleases,
  getAllOsReleases,
  getLicensedOsReleases,
  getLicensedOsystems,
};

export default osInfo;
