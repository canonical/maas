import { createSelector } from "@reduxjs/toolkit";

import { LicenseKeysMeta } from "@/app/store/licensekeys/types";
import type {
  LicenseKeys,
  LicenseKeysState,
} from "@/app/store/licensekeys/types";
import type { RootState } from "@/app/store/root/types";
import { generateBaseSelectors } from "@/app/store/utils";

const searchFunction = (licenseKey: LicenseKeys, term: string) =>
  licenseKey.osystem.includes(term) || licenseKey.distro_series.includes(term);

const defaultSelectors = generateBaseSelectors<
  LicenseKeysState,
  LicenseKeys,
  LicenseKeysMeta.PK
>(LicenseKeysMeta.MODEL, LicenseKeysMeta.PK, searchFunction);

/**
 * Returns true if license keys have errors
 * @param {RootState} state - Redux state
 * @returns {Boolean} License keys have errors
 */
const hasErrors = createSelector(
  [defaultSelectors.errors],
  (errors) => !!errors && Object.entries(errors).length > 0
);

/**
 * Get license keys for a given osystem and distro_series.
 * @param {RootState} state - The redux state.
 * @param {String} osystem - The operating system for the license key.
 * @param {String} distro_series - The distro series for the license key.
 * @returns {LicenseKeys} A matching license key.
 */
const getByOsystemAndDistroSeries = createSelector(
  [
    defaultSelectors.all,
    (
      _state: RootState,
      osystem: LicenseKeys["osystem"] | null | undefined,
      distro_series: LicenseKeys["distro_series"] | null | undefined
    ) => ({
      osystem,
      distro_series,
    }),
  ],
  (licensekeyItems, { osystem, distro_series }) =>
    licensekeyItems.filter(
      (item: LicenseKeys) =>
        item.osystem === osystem && item.distro_series === distro_series
    )[0]
);

const selectors = {
  ...defaultSelectors,
  hasErrors,
  getByOsystemAndDistroSeries,
};

export default selectors;
