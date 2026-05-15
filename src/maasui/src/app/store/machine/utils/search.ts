import fastDeepEqual from "fast-deep-equal";

import type { FetchFilters } from "@/app/store/machine/types";
import type { Tag } from "@/app/store/tag/types";
import type { FilterValue } from "@/app/utils/search/filter-handlers";
import FilterHandlers from "@/app/utils/search/filter-handlers";

export type ExtraData = {
  tags: Tag[];
};

export const WORKLOAD_FILTER_PREFIX = "workload-";

type APIFilters = Record<string, (number | string)[]>;

type SearchMappingFunc = (filter: FilterValue[]) => APIFilters | null;

type SearchAPIMappings = Record<string, SearchMappingFunc | string>;

/**
 * Generates a function to map a list of numbers to the highest value. This is
 * required as they are matched by 'greater than or equal to' and don't support
 * an array of values.
 * @param The API filter key that the value should be mapped to.
 * @returns A function to map to the min value.
 */
const mapNumber = (newKey: string) => (filter: FilterValue[]) => {
  return filter
    ? {
        [newKey]: filter.map((filterValue) =>
          typeof filterValue === "number"
            ? filterValue
            : parseInt(filterValue, 10)
        ),
      }
    : null;
};

// A mapping of search DSL names and values to API keys.
const searchAPIMappings: SearchAPIMappings = {
  cores: mapNumber("cpu_count"),
  cpu: mapNumber("cpu_count"),
  mac: "mac_address",
  ram: mapNumber("mem"),
  release: (releases) => {
    // Map release strings in the format osystem/distro_series (e.g.
    // "ubuntu/jammy") to the 'osystem' and distro_series' filters.
    const newFilters: {
      distro_series: string[];
      osystem: string[];
    } = {
      distro_series: [],
      osystem: [],
    };
    releases.forEach((release) => {
      const [osystem, distro_series] = release.toString().split("/");
      newFilters.distro_series.push(distro_series);
      newFilters.osystem.push(osystem);
    });
    return newFilters;
  },
  system_id: "id",
  q: (query) => (query.length > 0 ? { free_text: [query.join(" ")] } : null),
  vlan: "vlans",
};

class FilterMachineHandlers extends FilterHandlers {
  prefixedFilters = [{ filter: "workloads", prefix: "workload" }];

  /**
   * Parse the search DSL into filters to be sent to the API.
   * @param search A search DSL string.
   */
  parseFetchFilters = (search: string): FetchFilters => {
    // Parse the DSL into an object of values.
    const filters = this.getCurrentFilters(search);
    // Map the filters from the DSL names/filters to the API filters.
    const mappedValues = Object.entries(filters).reduce<APIFilters>(
      (fetchFilters, [filterName, filterValues]) => {
        // Get the mapping if there is one.
        const mapping =
          filterName in searchAPIMappings
            ? searchAPIMappings[filterName]
            : null;
        if (!mapping) {
          // Check if this is a filter that uses a prefix.
          const prefixedFilter = this.prefixedFilters.find(({ prefix }) =>
            filterName.startsWith(`${prefix}-`)
          );
          if (prefixedFilter) {
            // Prefixed filters are passed as key value string pairs e.g. {"workloads": "role:prod"}.
            fetchFilters = this._mergeFilters(
              {
                [prefixedFilter.filter]: [
                  // Remove the prefix from the start of the key.
                  `${filterName.replace(
                    `${prefixedFilter.prefix}-`,
                    ""
                  )}:${filterValues}`,
                ],
              },
              fetchFilters
            );
          } else {
            fetchFilters = this._mergeFilters(
              { [filterName]: filterValues },
              fetchFilters
            );
          }
        } else if (typeof mapping === "string") {
          // String mappings only require a name change.
          fetchFilters = this._mergeFilters(
            { [mapping]: filterValues },
            fetchFilters
          );
        } else {
          // Use a mapping function to get the new names and values.
          const newFilters = mapping(filterValues);
          if (newFilters) {
            // The mapping function returns an object containing new key names
            // and values, so this needs to be merged into the object of filters.
            fetchFilters = this._mergeFilters(newFilters, fetchFilters);
          }
        }
        return fetchFilters;
      },
      {}
    );
    // Map the filters from '!' to 'not_[key-name]'.
    return Object.entries(mappedValues).reduce<APIFilters>(
      (fetchFilters, [filterName, filterValues]) => {
        const includeValues = filterValues.filter(
          (filterValue) =>
            !(typeof filterValue === "string" && filterValue.startsWith("!"))
        );
        const excludeValues = filterValues.filter(
          (filterValue) =>
            typeof filterValue === "string" && filterValue.startsWith("!")
        );
        if (includeValues.length) {
          fetchFilters[filterName] = includeValues;
        }
        if (excludeValues.length) {
          fetchFilters[`not_${filterName}`] = excludeValues.map((filter) =>
            // Remove the starting '!'.
            typeof filter === "string" ? filter.substring(1) : filter
          );
        }
        return fetchFilters;
      },
      {}
    );
  };

  isNonEmptyFilter = (filter: string) => {
    return !fastDeepEqual(this.parseFetchFilters(filter), {});
  };

  /**
   * Merge a new filter into the existing list of filters. This is required
   * because multiple DSL filter names can be mapped to the same API key name.
   * @param newFilters The filters to be merged.
   * @param parsedFilters The existing object of parsed filters.
   */
  _mergeFilters = (
    newFilters: APIFilters,
    parsedFilters: APIFilters
  ): APIFilters => {
    Object.entries(newFilters).forEach(([newFilterName, newFilterValue]) => {
      if (newFilterName in parsedFilters) {
        const existingFilters = parsedFilters[newFilterName];
        // Combine the new and old filters.
        parsedFilters[newFilterName] = existingFilters.concat(newFilterValue);
      } else {
        parsedFilters[newFilterName] = newFilterValue;
      }
    }, {});
    return parsedFilters;
  };
}

export const FilterMachines = new FilterMachineHandlers();
