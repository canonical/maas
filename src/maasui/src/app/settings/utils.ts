import type { ConfigurationResponse, PublicConfigName } from "../apiclient";

import type { AnyObject } from "@/app/base/types";

/**
 * Returns whether two objects are equal when JSON.stringified. Note this
 * requires identical order of keys, and is only suitable for small objects.
 * @param {Object} obj1 - First object.
 * @param {Object} obj2 - Second object.
 * @returns {Boolean} Objects are equal when stringified.
 */
const simpleObjectEquality = <O = AnyObject>(obj1: O, obj2: O): boolean => {
  if (typeof obj1 === "object" && typeof obj2 === "object") {
    return JSON.stringify(obj1) === JSON.stringify(obj2);
  }
  return false;
};

/**
 * Extracts configuration values from the API response.
 * @param items - The API response items.
 * @param names - The names of the configurations to extract.
 * @returns An object containing the extracted configuration values.
 */
const getConfigsFromResponse = (
  items: ConfigurationResponse[],
  names: PublicConfigName[]
): Record<PublicConfigName, unknown> => {
  return items.reduce<Record<string, unknown>>((acc, item) => {
    if (names.includes(item.name as PublicConfigName)) {
      acc[item.name] = item.value;
    }
    return acc;
  }, {});
};

export { simpleObjectEquality, getConfigsFromResponse };
