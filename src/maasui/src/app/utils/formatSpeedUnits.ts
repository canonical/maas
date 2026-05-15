import { formatBytes } from "@canonical/maas-react-components";

/**
 * Format megabytes to an appropriate level of speed.
 * @param {Number} speedInMbytes The value in the supplied megabyte unit.
 * @returns {String} Formatted value and unit.
 */
export const formatSpeedUnits = (speedInMbytes: number): string => {
  const adjusted =
    speedInMbytes > 1
      ? formatBytes({ value: speedInMbytes, unit: "MB" })
      : { unit: "MB", value: speedInMbytes };
  return `${Math.floor(adjusted.value)} ${adjusted.unit[0]}bps`;
};
