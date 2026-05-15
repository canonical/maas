/**
 * Whether a value can be used in a sort function to check for >, < or ===.
 */
export const isComparable = (value: unknown): value is number | string =>
  typeof value === "number" || typeof value === "string";
