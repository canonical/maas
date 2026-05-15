/**
 * Returns whether a version string is newer than another version string.
 * @param {String} versionA - a dot separated version string, e.g. "2.8.0"
 * @param {String} versionB - the version string to compare against
 * @returns {Boolean} versionA is newer than versionB
 */
export const isVersionNewer = (versionA: string, versionB: string): boolean => {
  const partsA = versionA.split(".");
  const partsB = versionB.split(".");
  const numParts =
    partsA.length > partsB.length ? partsA.length : partsB.length;

  for (let i = 0; i < numParts; i++) {
    if ((parseInt(partsA[i]) || 0) !== (parseInt(partsB[i]) || 0)) {
      return (parseInt(partsA[i]) || 0) > (parseInt(partsB[i]) || 0);
    }
  }
  return false;
};
