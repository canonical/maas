/**
 * Returns whether two arrays contain the same items, but not necessarily in the
 * same order.
 * @param arr1 - the array of items to check
 * @param arr2 - the array of items to check against
 * @returns Whether the arrays contain the same items.
 */
export const arrayItemsEqual = (arr1: unknown[], arr2: unknown[]): boolean =>
  arr1.length === arr2.length && arr1.every((item) => arr2.includes(item));
