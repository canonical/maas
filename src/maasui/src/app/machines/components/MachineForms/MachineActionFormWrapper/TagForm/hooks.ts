import { useEffect, useState } from "react";

import { usePrevious } from "@canonical/react-components";
import { nanoid } from "@reduxjs/toolkit";
import fastDeepEqual from "fast-deep-equal";
import { useFormikContext } from "formik";
import { useDispatch, useSelector } from "react-redux";

import type { TagFormValues } from "./types";

import type { APIError } from "@/app/base/types";
import type { FetchFilters } from "@/app/store/machine/types";
import type { SelectedMachines } from "@/app/store/machine/types/base";
import { FilterMachines } from "@/app/store/machine/utils";
import { selectedToSeparateFilters } from "@/app/store/machine/utils/common";
import type { UseFetchQueryOptions } from "@/app/store/machine/utils/hooks";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag, TagMeta } from "@/app/store/tag/types";
import type { TagStateList } from "@/app/store/tag/types/base";
import { toFormikNumber } from "@/app/utils";

/**
 * Get the tag objects for the tag ids that have been selected in the form.
 */
export const useSelectedTags = (key: keyof TagFormValues): Tag[] => {
  const { values } = useFormikContext<TagFormValues>();
  // The Formik values are strings so we need to convert these into numbers so
  // they can be used in the selector.
  const tagIds = values[key].reduce<Tag[TagMeta.PK][]>((tagList, id) => {
    const idNumber = toFormikNumber(id);
    if (idNumber) {
      tagList.push(idNumber);
    }
    return tagList;
  }, []);
  const selectedTags = useSelector((state: RootState) =>
    tagSelectors.getByIDs(state, tagIds)
  );
  return selectedTags;
};

/**
 * Filter tags for those that have not been added or removed.
 * @param tags A list of tags to filter.
 * @returns A list of unchanged tags.
 */
export const useUnchangedTags = (tags: Tag[]): Tag[] => {
  const { values } = useFormikContext<TagFormValues>();
  // Use `find` instead of `includes` as we need to convert the stored values
  // to numbers (Formik returns either strings or numbers depending on the
  // render cycle).
  return tags.filter(
    (tag) =>
      !values.added.find((tagId) => toFormikNumber(tagId) === tag.id) &&
      !values.removed.find((tagId) => toFormikNumber(tagId) === tag.id)
  );
};

export const useFetchTags = (
  options?: {
    filters: FetchFilters | null;
  },
  queryOptions?: UseFetchQueryOptions
): {
  callId: string | null;
  loaded: boolean;
  loading: boolean;
  errors: APIError;
  tags: TagStateList["items"];
} => {
  const { isEnabled } = queryOptions || { isEnabled: true };
  const previousIsEnabled = usePrevious(isEnabled);
  const [callId, setCallId] = useState<string | null>(null);
  const previousCallId = usePrevious(callId);
  const previousOptions = usePrevious(options, false);
  const dispatch = useDispatch();
  const tagsList = useSelector((state: RootState) =>
    tagSelectors.list(state, callId)
  );
  const errors = useSelector((state: RootState) =>
    tagSelectors.listErrors(state, callId)
  );
  const loaded = useSelector((state: RootState) =>
    tagSelectors.listLoaded(state, callId)
  );
  const loading = useSelector((state: RootState) =>
    tagSelectors.listLoading(state, callId)
  );

  useEffect(() => {
    return () => {
      if (callId) {
        dispatch(tagActions.removeRequest(callId));
      }
    };
  }, [callId, dispatch]);

  useEffect(() => {
    // undefined, null and {} are all equivalent i.e. no filters so compare the
    // current and previous filters using an empty object if the filters are falsy.
    if (
      (isEnabled && !fastDeepEqual(options || {}, previousOptions || {})) ||
      !callId
    ) {
      setCallId(nanoid());
    }
  }, [callId, options, previousOptions, isEnabled]);

  useEffect(() => {
    if (
      (isEnabled && callId && callId !== previousCallId) ||
      (isEnabled !== previousIsEnabled && callId)
    ) {
      dispatch(
        tagActions.fetch(
          options?.filters
            ? {
                node_filter: options.filters,
              }
            : undefined,
          callId
        )
      );
    }
  }, [callId, dispatch, options, previousCallId, isEnabled, previousIsEnabled]);

  return {
    callId,
    loaded,
    loading,
    errors,
    tags: isEnabled ? tagsList || [] : [],
  };
};

export const useFetchTagsForSelected = (options: {
  selectedMachines?: SelectedMachines | null;
  searchFilter?: string;
}): {
  loaded: boolean;
  loading: boolean;
  errors: APIError;
  tags: Tag[];
} => {
  const { itemFilters, groupFilters } = selectedToSeparateFilters(
    options.selectedMachines || null
  );
  const searchFilter = options.searchFilter
    ? FilterMachines.parseFetchFilters(options.searchFilter)
    : {};
  const {
    loading: loadingForItemFilters,
    loaded: tagsForItemFiltersLoaded,
    tags: tagsForItemFilters,
    errors: errorsForItemFilters,
  } = useFetchTags(
    {
      filters: {
        ...itemFilters,
        ...searchFilter,
      },
    },
    {
      isEnabled: itemFilters !== null,
    }
  );
  const { loading, loaded, tags, errors } = useFetchTags(
    {
      filters: {
        ...groupFilters,
        ...searchFilter,
      },
    },
    {
      isEnabled: groupFilters !== null,
    }
  );

  return {
    loaded: tagsForItemFiltersLoaded && loaded,
    loading: loadingForItemFilters || loading,
    errors:
      errorsForItemFilters || errors ? errorsForItemFilters || errors : null,
    tags: [
      ...(tags ? tags : []),
      ...(tagsForItemFilters ? tagsForItemFilters : []),
    ],
  };
};

export type TagIdCountMap = Map<Tag[TagMeta.PK], number>;
