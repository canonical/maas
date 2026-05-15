/**
 * Formats a string into a valid MAC address as its being typed into an input.
 *
 * @param {String} value - original MAC address
 * @returns {String} formatted MAC address
 */

export const formatMacAddress = (value: string): string => {
  const hexValues = value.replace(/:/g, "");

  if (hexValues.length > 10) {
    const firstTenValues = hexValues.slice(0, 10);
    const lastValues = hexValues.slice(10);

    return firstTenValues.replace(/([0-9A-Za-z]{2})/g, "$1:") + lastValues;
  } else {
    return hexValues.replace(/([0-9A-Za-z]{2})/g, "$1:");
  }
};
