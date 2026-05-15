import type { Selector } from "@reduxjs/toolkit";
import { createSelector } from "@reduxjs/toolkit";
import { createCachedSelector } from "re-reselect";

import type { RootState } from "@/app/store/root/types";
import type { CommonStates, CommonStateTypes } from "@/app/store/utils";

/**
 * @template I - A model item type e.g. DHCPSnippet
 */
type SearchFunction<I> = (item: I, term: string) => boolean;

/**
 * @template S - The model state type e.g. DHCPSnippetState.
 * @template I - A model that is used as an an array of items on the provided
 *               state e.g. DHCPSnippet
 * @template K - A model key e.g. "id"
 */
type BaseSelectors<
  // Any of the allowed state types.
  S extends CommonStateTypes,
  // The model type needs to be a reference to the supplied state so that
  // TypeScript can validate whether the key exists on the model.
  // S["items"] will refer to something like `items: DHCPSnippet[];` and `[0]`
  // will retrieve the type of the model e.g. `DHCPSnippet`.
  // See: https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-1.html#keyof-and-lookup-types
  I extends S["items"][0],
  // A model key as a reference to the supplied state item.
  K extends keyof I,
> = {
  all: (state: RootState) => S["items"];
  // This method is generated using createSelector so it results
  // in a function of type `Selector`.
  count: Selector<RootState, number>;
  errors: (state: RootState) => S["errors"];
  // This method is generated using createSelector with parameters so it results
  // in a function of type `OutputParametricSelector`.
  getById: (state: RootState, id: I[K] | null | undefined) => I | null;
  loaded: (state: RootState) => S["loaded"];
  loading: (state: RootState) => S["loading"];
  saved: (state: RootState) => S["saved"];
  saving: (state: RootState) => S["saving"];
  search: (state: RootState, term: string) => I[];
};

/**
 * @template S - The model state type e.g. DHCPSnippetState.
 * @template I - A model that is used as an an array of items on the provided
 *               state e.g. DHCPSnippet
 * @template {string} K - A model key e.g. "id"
 * @param {string} name - The root state key of the model e.g. "dhcpsnippet".
 * @param {K} indexKey - The key of the id field e.g. "id" or "system_id".
 * @param {SearchFunction} searchFunction - The function to match items
 *                                          when filtering.
 */
export const generateBaseSelectors = <
  // Any of the allowed state types.
  S extends CommonStateTypes,
  // A model key as a reference from the supplied state. For more explanation
  // see the BaseSelectors type definition above.
  I extends S["items"][0],
  // A model key as a reference from the supplied model.
  K extends keyof I,
>(
  name: keyof CommonStates,
  indexKey: K,
  // Provide a default search function for models that don't use it.
  searchFunction: SearchFunction<I> = () => false
): BaseSelectors<S, I, K> => {
  const all = (state: RootState) => state[name].items;
  const count = createSelector([all], (items) => items.length);
  const errors = (state: RootState) => state[name].errors;
  const loaded = (state: RootState) => state[name].loaded;
  const loading = (state: RootState) => state[name].loading;
  const saved = (state: RootState) => state[name].saved;
  const saving = (state: RootState) => state[name].saving;
  const search = createSelector(
    [all, (_state: RootState, term: string) => term],
    (items, term) => (items as I[]).filter((item) => searchFunction(item, term))
  );
  const getById = createCachedSelector(
    [all, (_state: RootState, id: I[K] | null | undefined) => id],
    (items, id) => {
      // `0` is a valid id for some models (e.g. fabric) so do a strict check.
      if (id === null || id === undefined) {
        return null;
      }
      return (items as I[]).find((item) => item[indexKey] === id) || null;
    }
  )((_state, id) => id || "");

  return {
    all,
    count,
    errors,
    getById,
    loaded,
    loading,
    saved,
    saving,
    search,
  };
};
