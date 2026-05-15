/**
 * Get the next valid name in the sequence.
 * @param names - A list of existing names.
 * @param prefix - The name prefix e.g. "eth"
 * @param startIndex - The number to start the sequence on.
 * @returns The new name.
 */
export const getNextName = (
  names: string[],
  prefix: string,
  startIndex = 0
): string => {
  let idx = startIndex;
  names.forEach((name) => {
    // Check that the string starts with the prefix to prevent false positives
    // if the prefix exists somewhere else in the string.
    if (name.startsWith(prefix)) {
      // Remove the prefix and try and turn the remaining string into a number.
      const counter = Number(name.replace(prefix, ""));
      // If this counter is a valid number and is higher than the stored id then store a new one.
      if (!isNaN(counter) && counter >= idx) {
        idx = counter + 1;
      }
    }
  });
  return `${prefix}${idx}`;
};
