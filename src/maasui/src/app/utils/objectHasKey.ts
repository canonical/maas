/**
 * Narrow a string to whether it is a valid key for an object or not. This can
 * be used as a type guard e.g. when the object type is a union.
 */
export const objectHasKey = <K extends string, O extends Record<K, O[K]>>(
  key: K,
  object: O
): object is O & Record<K, string> => {
  return key && object && key in object;
};
