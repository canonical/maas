import { useState } from "react";

import type { Sort } from "../types";
import { SortDirection } from "../types";

import { isComparable } from "@/app/utils";

type SortValueGetter<I, K extends string | null, A = null> = (
  sortKey: K,
  item: I,
  args?: A
) => number | string | null;

export type TableSort<I, K extends string | null, A = null> = {
  currentSort: Sort<K>;
  sortRows: (items: I[], args?: A) => I[];
  updateSort: (newSort: K) => void;
};

/**
 * Handle sorting in tables.
 * @param sortValueGetter - The function that determines what value to use when comparing row objects.
 * @param initialSort - The initial sort key and direction on table render.
 * @param sortFunction - A function to be used to sort the items.
 * @returns The properties and helper functions to use in table sorting.
 */
export const useTableSort = <I, K extends string | null, A = null>(
  sortValueGetter: SortValueGetter<I, K, A>,
  initialSort: Sort<K>,
  sortFunction?: (
    itemA: I,
    itemB: I,
    key: Sort<K>["key"],
    args: A | undefined,
    direction: Sort<K>["direction"],
    items: I[]
  ) => -1 | 0 | 1
): TableSort<I, K, A> => {
  const [currentSort, setCurrentSort] = useState(initialSort);

  // Update current sort depending on whether the same sort key was clicked.
  const updateSort = (newSortKey: K) => {
    const { key, direction } = currentSort;

    if (newSortKey === key) {
      if (direction === SortDirection.ASCENDING) {
        setCurrentSort({ key: null, direction: SortDirection.NONE });
      } else {
        setCurrentSort({ key, direction: SortDirection.ASCENDING });
      }
    } else {
      setCurrentSort({ key: newSortKey, direction: SortDirection.DESCENDING });
    }
  };

  // Sort rows according to sortValueGetter. Additional arguments will need to be
  // passed to both the sortValueGetter and sortRows functions.
  const sortRows = (items: I[], args?: A): I[] => {
    const { key, direction } = currentSort;

    const sortFunctionGenerator = (itemA: I, itemB: I) => {
      if (sortFunction) {
        return sortFunction(itemA, itemB, key, args, direction, items);
      }
      const sortA = key ? sortValueGetter(key, itemA, args) : null;
      const sortB = key ? sortValueGetter(key, itemB, args) : null;

      if (direction === "none" || (!sortA && !sortB)) {
        return 0;
      }
      if (
        (sortB && !sortA) ||
        (isComparable(sortA) && isComparable(sortB) && sortA < sortB)
      ) {
        return direction === "descending" ? -1 : 1;
      }
      if (
        (sortA && !sortB) ||
        (isComparable(sortA) && isComparable(sortB) && sortA > sortB)
      ) {
        return direction === "descending" ? 1 : -1;
      }
      return 0;
    };

    return [...items].sort(sortFunctionGenerator);
  };

  return { currentSort, sortRows, updateSort };
};
