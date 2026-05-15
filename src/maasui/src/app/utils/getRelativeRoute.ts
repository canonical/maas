/**
 * Returns a relative route using the base provided.
 * @param route - A route to extract the relative path from.
 * @param base - A base URL.
 * @returns A relative route.
 */
export const getRelativeRoute = (route: string, base: string): string =>
  route.replace(base, "").replace(/^\//, "");
