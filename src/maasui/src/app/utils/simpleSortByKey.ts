/**
 * Simple sort objects by key value.
 *
 * @param key - the key of the objects to sort by
 * @param config - config object
 * @param config.reverse - whether to reverse the results
 * @returns sort function
 */
export const simpleSortByKey =
  <O, K extends keyof O>(
    key: K,
    { alphanumeric, reverse }: { alphanumeric?: boolean; reverse?: boolean } = {
      alphanumeric: false,
      reverse: false,
    }
  ): ((a: O, b: O) => number) =>
  (a: O, b: O) => {
    const paramA = a[key];
    const paramB = b[key];
    if (
      alphanumeric &&
      typeof paramA === "string" &&
      typeof paramB === "string"
    ) {
      return paramA.localeCompare(paramB, "en", { numeric: true });
    }
    if (paramA > paramB) return reverse ? -1 : 1;
    if (a[key] < paramB) return reverse ? 1 : -1;
    return 0;
  };
