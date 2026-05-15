/**
 * Capitalises the first character of a string.
 * @param {string} - text to capitalise
 */
export const capitaliseFirst = (text: string): string => {
  const [first, ...rest] = text;
  return [first.toLocaleUpperCase(), ...rest].join("");
};
