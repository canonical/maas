type KebabToCamelCase<S extends string> =
  S extends `${infer FirstPart}-${infer FirstLetter}${infer LastPart}`
    ? `${FirstPart}${Uppercase<FirstLetter>}${KebabToCamelCase<LastPart>}`
    : S;

/**
 * Convert a kebab case string into a camel case string,
 * e.g. my-string => myString
 *
 * @param {string} string - the kebab case string to convert
 * @returns {string} camel case string
 */
export function kebabToCamelCase<S extends string>(
  str: S
): KebabToCamelCase<S> {
  return str.replace(/-([a-z])/g, (g) =>
    g[1].toUpperCase()
  ) as KebabToCamelCase<S>;
}
