/**
 * Returns whether some, but not all, of an array is in another array.
 * @param {unknown[]} arr1 - the array of items to check
 * @param {unknown[]} arr2 - the array of items to check against
 * @returns {boolean} Some, but not all, of `arr1` is in `arr2`
 */
export const someNotAll = (arr1: unknown[], arr2: unknown[]): boolean =>
  arr1.length > 0 &&
  arr2.length > 0 &&
  arr1.some((item) => !arr2.includes(item));
