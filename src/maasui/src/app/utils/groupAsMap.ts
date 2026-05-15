/**
 * Group an array of objects by a key getter function into an ES6 Map.
 *
 * @param {array{}} arr - the array of objects to group
 * @param {function} keyGetter - the key getter function to group by, e.g item => item.name
 * @returns {Map} grouped Map
 */

import type { ValueOf } from "@canonical/react-components";

import type { AnyObject } from "@/app/base/types";

export const groupAsMap = <I extends AnyObject>(
  arr: I[],
  keyGetter: (item: I) => ValueOf<I>
): Map<ValueOf<I>, I[]> => {
  const map = new Map();
  arr.forEach((item) => {
    const key = keyGetter(item);
    const collection = map.get(key);
    if (!collection) {
      map.set(key, [item]);
    } else {
      collection.push(item);
    }
  });
  return map;
};
