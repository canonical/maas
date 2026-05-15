import { createCachedSelector } from "re-reselect";
import { createSelector } from "reselect";

import type { RootState } from "@/app/store/root/types";
import { TagMeta } from "@/app/store/tag/types";
import type { Tag, TagState } from "@/app/store/tag/types";
import { generateBaseSelectors } from "@/app/store/utils";

const searchFunction = (tag: Tag, term: string) => tag.name.includes(term);

const defaultSelectors = generateBaseSelectors<TagState, Tag, TagMeta.PK>(
  TagMeta.MODEL,
  TagMeta.PK,
  searchFunction
);

const tagState = (state: RootState): TagState => state[TagMeta.MODEL];

const getTagsFromIds = (
  tags: Tag[],
  tagIDs: Tag[TagMeta.PK][] | null
): Tag[] => {
  if (!tagIDs) {
    return [];
  }
  return tagIDs.reduce<Tag[]>((filteredTags, tagID) => {
    const tag = tags.find((tag) => tag.id === tagID);
    if (tag) {
      filteredTags.push(tag);
    }
    return filteredTags;
  }, []);
};

/**
 * Get a list of tags from a list of their IDs.
 * @param state - The redux state.
 * @param ids - A list of tag IDs.
 * @returns A list of tags.
 */
const getByIDs = createCachedSelector(
  defaultSelectors.all,
  (_state: RootState, tagIDs: Tag[TagMeta.PK][] | null) => tagIDs,
  (allTags, tagIDs) => getTagsFromIds(allTags, tagIDs)
)((_state, tagIDs) => tagIDs?.join(",") || ""); // cache by tagIDs

const getList = (tagState: TagState, callId: string | null | undefined) =>
  callId && callId in tagState.lists ? tagState.lists[callId] : null;

/**
 * Get the errors for a tag list request with a given callId
 */
const listErrors = createSelector(
  [tagState, (_state: RootState, callId: string | null | undefined) => callId],
  (tagState, callId) => getList(tagState, callId)?.errors || null
);

/**
 * Get the loaded state for a tag list request with a given callId.
 */
const listLoaded = createSelector(
  [tagState, (_state: RootState, callId: string | null | undefined) => callId],
  (tagState, callId) => getList(tagState, callId)?.loaded ?? false
);

/**
 * Get the loading state for a tag list request with a given callId.
 */
const listLoading = createSelector(
  [tagState, (_state: RootState, callId: string | null | undefined) => callId],
  (tagState, callId) => getList(tagState, callId)?.loading ?? false
);

/**
 * Get tags in a list request.
 * @param state - The redux state.
 * @param callId - A list request id.
 * @param selected - Whether to filter for selected tags.
 * @returns A list of tags.
 */
const list = createSelector(
  [
    tagState,
    (_state: RootState, callId: string | null | undefined) => ({
      callId,
    }),
  ],
  (tagState, { callId }) => getList(tagState, callId)?.items ?? null
);

/**
 * Get a list of manual tags.
 * @param state - The redux state.
 * @returns A list of manual tags.
 */
const getManual = createSelector([defaultSelectors.all], (tags) =>
  tags.filter(({ definition }) => !definition)
);

/**
 * Get a list of automatic tags.
 * @param state - The redux state.
 * @returns A list of automatic tags.
 */
const getAutomatic = createSelector([defaultSelectors.all], (tags) =>
  // Automatic tags have a definition.
  tags.filter(({ definition }) => !!definition)
);

/**
 * Get a list of tags from a list of their IDs.
 * @param state - The redux state.
 * @param ids - A list of tag IDs.
 * @returns A list of tags.
 */
const getAutomaticByIDs = createSelector(
  [
    getAutomatic,
    (_state: RootState, tagIDs: Tag[TagMeta.PK][] | null) => tagIDs,
  ],
  (automaticTags, tagIDs) => getTagsFromIds(automaticTags, tagIDs)
);

/**
 * Get a list of tags from a list of their IDs.
 * @param state - The redux state.
 * @param ids - A list of tag IDs.
 * @returns A list of tags.
 */
const getManualByIDs = createSelector(
  [getManual, (_state: RootState, tagIDs: Tag[TagMeta.PK][] | null) => tagIDs],
  (manualTags, tagIDs) => getTagsFromIds(manualTags, tagIDs)
);

/**
 * Get a tag by its name.
 * @param state - The redux state.
 * @param name - The tag's name.
 * @returns A tag.
 */
const getByName = createSelector(
  [defaultSelectors.all, (_state: RootState, name: Tag["name"] | null) => name],
  (tags, name) => {
    if (!name) {
      return null;
    }
    return tags.find((tag) => tag.name === name) ?? null;
  }
);

export enum TagSearchFilter {
  All = "all",
  Manual = "manual",
  Auto = "auto",
}

/**
 * Get tags that match search terms and filters.
 * @param state - The redux state.
 * @param terms - The terms to match against.
 * @param filter - A .
 * @returns A filtered list of tags.
 */
const search = createSelector(
  [
    defaultSelectors.all,
    (
      _state: RootState,
      terms: string | null | undefined,
      filter: TagSearchFilter | null | undefined
    ) => ({
      terms,
      filter,
    }),
  ],
  (tags: Tag[], { terms, filter }) => {
    if (filter && filter !== TagSearchFilter.All) {
      tags = tags.filter(({ definition }) =>
        filter === TagSearchFilter.Auto ? !!definition : !definition
      );
    }
    if (terms) {
      tags = tags.filter((tag) => searchFunction(tag, terms));
    }
    return tags;
  }
);

const selectors = {
  ...defaultSelectors,
  getByIDs,
  getByName,
  getAutomatic,
  getAutomaticByIDs,
  getManual,
  getManualByIDs,
  list,
  listErrors,
  listLoaded,
  listLoading,
  search,
};

export default selectors;
