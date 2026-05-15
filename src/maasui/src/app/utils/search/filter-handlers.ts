export type FilterValue = number | string;

export type Filters = Record<string, FilterValue[]>;

export type PrefixedFilter = {
  filter: string;
  prefix: string;
};

export const isFilterValue = (itemValue: unknown): itemValue is FilterValue => {
  return (
    (typeof itemValue === "string" || typeof itemValue === "number") &&
    (!!itemValue || itemValue === 0)
  );
};

export const isFilterValueArray = (
  itemValue: unknown
): itemValue is FilterValue[] => {
  return Array.isArray(itemValue) && isFilterValue(itemValue[0]);
};

export default class FilterHandlers {
  prefixedFilters: PrefixedFilter[];

  constructor(prefixedFilters: PrefixedFilter[] = []) {
    this.prefixedFilters = prefixedFilters;
  }

  // Get a prefixed filter, if it is in the prefixed list.
  _getPrefixedFilter = (type: keyof Filters): PrefixedFilter | null =>
    this.prefixedFilters.find(({ filter }) => filter === type) || null;

  // Generate a prefixed filter key.
  _getPrefixedFilterKey = (
    type: keyof Filters,
    value: FilterValue
  ): string | null => {
    const prefixedFilter = this._getPrefixedFilter(type);
    if (!prefixedFilter) {
      return null;
    }
    return value.toString().startsWith(`${prefixedFilter.prefix}-`)
      ? value.toString()
      : `${prefixedFilter.prefix}-${value}`;
  };

  // Whether this is a prefixed filter key.
  _isPrefixedFilterKey = (key: string): boolean =>
    this.prefixedFilters.some(({ prefix }) => key.startsWith(`${prefix}-`));

  // Return a new empty filter;
  getEmptyFilter = (): Filters => ({
    // "q" is for free search, i.e. not a specific item attribute. "q" has
    // been chosen because it shouldn't conflict with any item attributes and
    // also is the key name in the search URL query params.
    q: [],
  });

  // Return all of the currently active filters for the given search.
  getCurrentFilters = (search?: string): Filters => {
    const filters = this.getEmptyFilter();
    if (!search) {
      return filters;
    }
    // Match filters with parens e.g. 'status:(new,deployed)'.
    // Then: match filters without parens e.g. 'status:new,deployed' or 'status'
    const filterMatchingRegex = search.matchAll(
      /(\b[\w-]+:!*\([^)]+\))|(!*\w+\S*)/g
    );
    [...filterMatchingRegex].forEach(([group]) => {
      // Get the filter name and values (if supplied).
      const groupParts = group.split(/:(.+)/);
      const [groupName] = groupParts;
      let [, groupValues] = groupParts;
      if (groupValues) {
        const allNegated = groupValues.startsWith("!(");
        if (allNegated) {
          // Remove the "!"
          groupValues = groupValues.substr(1);
        } else if (groupValues.startsWith("!!(")) {
          // Remove the "!!"
          groupValues = groupValues.substr(2);
        }
        if (groupValues.startsWith("(") !== groupValues.endsWith(")")) {
          // The filter must contain opening and closing parens or neither.
          return;
        }
        // Remove the surrounding parens.
        const cleanValues = groupValues.match(/[^(|^)]+/g);
        if (!cleanValues) {
          // If there are no values inside the parens...
          if (this._isPrefixedFilterKey(groupName)) {
            // This is only valid for prefixed filters, in which the value in
            // the parens is treated as a free text search for a particular
            // prefixed filter. An empty string matches any item with that
            // prefixed filter.
            filters[groupName] = [""];
          } else {
            return;
          }
        } else {
          // Split the comma separated values and add the filter.
          let valueList = cleanValues[0].split(",");
          if (allNegated) {
            valueList = valueList.map((value) => `!${value}`);
          }
          filters[groupName] = valueList;
        }
      } else if (this._isPrefixedFilterKey(group)) {
        // This is a prefix filter without parens (e.g. "workspace-blue") so
        // match against any item with that prefix filter.
        filters[group] = [""];
      } else if (!group.includes(":")) {
        // This is a free search value.
        filters.q?.push(groupName);
      }
    });
    return filters;
  };

  // Convert "filters" into a search string.
  filtersToString = (filters: Filters): string => {
    let search =
      filters.q && filters.q.length > 0 ? `${filters.q?.join(" ")}` : "";
    Object.entries(filters).forEach(([type, terms]) => {
      // Skip empty and skip "q" as it gets appended at the
      // beginning of the search.
      if (terms.length === 0 || type === "q") {
        return;
      }
      search += ` ${type}:(${terms.join(",")})`;
    });
    return search.trim();
  };

  // Return the index of the value in the type for the filter.
  _getFilterValueIndex = (
    filters: Filters,
    type: keyof Filters,
    value: FilterValue
  ): number => {
    const values = filters[type];
    if (!values) {
      return -1;
    }
    const lowerValues = values.map((value) => value.toString().toLowerCase());
    return lowerValues.indexOf(value.toString().toLowerCase());
  };

  // Whether the type and value are in the filters.
  isFilterActive = (
    filters: Filters | null,
    type: keyof Filters,
    value: FilterValue,
    exact = false
  ): boolean => {
    if (!filters) {
      return false;
    }
    const prefixedFilter = this._getPrefixedFilter(type);
    if (prefixedFilter) {
      // A prefixed filter is considered active if it simply exists.
      return Object.keys(filters).some(
        (filter) => filter === this._getPrefixedFilterKey(type, value)
      );
    }
    const values = filters[type];
    if (!values) {
      return false;
    }
    if (exact) {
      value = `=${value}`;
    }
    return this._getFilterValueIndex(filters, type, value) !== -1;
  };

  /**
   * Toggles a prefixed filter.
   * @param filters - The initial filters.
   * @param prefixFilter - The prefix filter.
   * @param prefixValue - The prefix filter value to toggle, with or without the
   * prefix.
   * @param shouldExist - An optional value for whether the value should
   * exist or not i.e. if true and the value exists there will be no change and
   * vice versa.
   * @returns The updated filters.
   */
  _togglePrefixedFilter = (
    filters: Filters,
    prefixFilter: PrefixedFilter["filter"],
    prefixValue: string,
    shouldExist?: boolean
  ): Filters => {
    // If the provided value does not start with the prefix then prepend it.
    const prefixKey = this._getPrefixedFilterKey(prefixFilter, prefixValue);
    if (!prefixKey) {
      return filters;
    }
    const exists = this.isFilterActive(filters, prefixFilter, prefixKey);
    const newExist =
      shouldExist === undefined
        ? !this.isFilterActive(filters, prefixFilter, prefixKey)
        : shouldExist;
    if (!exists) {
      if (newExist) {
        if (typeof filters[prefixKey] === "undefined") {
          filters[prefixKey] = [];
        }
        filters[prefixKey].push("");
      }
    } else if (exists) {
      if (!newExist) {
        delete filters[prefixKey];
      }
    }
    return filters;
  };

  /**
   * Toggles a filter on or off based on type and value.
   * @param filters - The initial filters.
   * @param type - The filter key.
   * @param value - The filter value to toggle.
   * @param exact - Optional value for whether the value should
   * exactly match.
   * @param shouldExist - An optional value for whether the value should
   * exist or not i.e. if true and the value exists there will be no change and
   * vice versa.
   * @returns The updated filters.
   */
  toggleFilter = (
    filters: Filters,
    type: keyof Filters,
    value: FilterValue,
    exact?: boolean,
    shouldExist?: boolean
  ): Filters => {
    // If this has been passed a prefix filter type then the value will be a
    // prefix key, so toggle the key instead of the type.
    if (
      this._getPrefixedFilter(type) &&
      typeof type === "string" &&
      typeof value === "string"
    ) {
      return this._togglePrefixedFilter(filters, type, value, shouldExist);
    }
    if (exact) {
      value = "=" + value;
    }
    const idx = this._getFilterValueIndex(filters, type, value);
    const exists = idx !== -1;
    if (!exists) {
      if (shouldExist === undefined ? true : shouldExist) {
        if (typeof filters[type] === "undefined") {
          filters[type] = [];
        }
        filters[type].push(value);
      }
    } else if (exists) {
      if (shouldExist === undefined ? true : !shouldExist) {
        filters[type].splice(idx, 1);
        if (filters[type].length === 0) {
          delete filters[type];
        }
      }
    }
    return filters;
  };

  // Convert a URL query string into a filter object.
  queryStringToFilters = (queryString: string): Filters => {
    const filters = this.getEmptyFilter();
    [...new URLSearchParams(queryString)].forEach(([name, values]) => {
      if (!values.length) {
        // There are no values for this filter so ignore it.
        return;
      }
      filters[name] = values.split(",");
    });
    return filters;
  };

  // Convert a filter object into a URL query string.
  filtersToQueryString = (filters: Filters): string => {
    // Shallow copy the object, this should be good enough for the manipulation
    // we do below.
    const copiedFilters: Record<string, string> = {};
    // Remove empty filters.
    Object.keys(filters).forEach((filter) => {
      // Remove in:selected in in:!selected from the URL as we don't also persist
      // the selected states of items.
      if (filters[filter].length > 0 && filter !== "in") {
        copiedFilters[filter] = filters[filter].join(",");
      }
    });
    return `?${new URLSearchParams(copiedFilters).toString()}`;
  };
}
