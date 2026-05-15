/**
 * Replaces extra spaces and newlines with a single space.
 */
export const unindentString = (str: string): string =>
  str.replace(/\s+/g, " ").trim();
