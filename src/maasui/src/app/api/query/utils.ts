/**
 * Selector function to get the count of items in an array.
 * @template T
 * @returns {function(T[] | undefined): number} A function that takes an array of items and returns the count of items.
 */
export const selectItemsCount = <T>() => {
  return (data: T[] | undefined): number => data?.length ?? 0;
};

/**
 * Selector function to find an item by its ID.
 * @template T
 * @param {number | null} id - The ID of the item to find.
 * @returns {function(T[]): T | undefined} A function that takes an array of items and returns the item with the specified ID.
 */
export const selectById = <T extends { id: number | null }>(
  id: number | null
) => {
  return (data: T[]): T | null => data.find((item) => item.id === id) || null;
};
