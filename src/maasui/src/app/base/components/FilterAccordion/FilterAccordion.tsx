import type { ReactNode, AriaAttributes } from "react";
import { useMemo, useState } from "react";

import {
  Accordion,
  Button,
  ContextualMenu,
  List,
} from "@canonical/react-components";
import classNames from "classnames";

import type { FilterValue } from "@/app/utils/search/filter-handlers";
import type FilterItems from "@/app/utils/search/filter-items";

// The key for the filter, this will usually be a model attribute.
type FilterKey = string;

// A mapping between the available values for a filter and the count of items
// that have that value.
type FilterValues = Map<FilterValue, number>;

// A mapping between filters and the available values and counts.
type FilterSections = Map<FilterKey, FilterValues>;

export type Props<I, PK extends keyof I> = Pick<
  AriaAttributes,
  "aria-label"
> & {
  disabled?: boolean;
  filterNames: Map<FilterKey, string>;
  filterOrder: FilterKey[];
  filtersToString: FilterItems<I, PK>["filtersToString"];
  filterString?: string;
  getCurrentFilters: FilterItems<I, PK>["getCurrentFilters"];
  getValue: (item: I, filter: FilterKey) => FilterValue | FilterValue[] | null;
  getValueDisplay?: (filter: FilterKey, value: FilterValue) => ReactNode;
  isFilterActive: FilterItems<I, PK>["isFilterActive"];
  items: I[];
  onUpdateFilterString: (filterString: string) => void;
  toggleFilter: FilterItems<I, PK>["toggleFilter"];
};

// An accordion section.
type Section = {
  title?: string;
  content: ReactNode;
  key: string;
};

export enum Labels {
  Toggle = "Filters",
}

const getFilters = <I, PK extends keyof I>(
  items: Props<I, PK>["items"],
  filterOrder: Props<I, PK>["filterOrder"],
  getValue: Props<I, PK>["getValue"]
) => {
  const filters: FilterSections = new Map();
  items.forEach((item) => {
    filterOrder.forEach((filter) => {
      const value = getValue(item, filter);
      // Ignore this section if this is not a value that can be filtered by:
      if (!value) {
        return;
      }
      // Turn everything into an array so we can loop over all values.
      const valueArray = Array.isArray(value) ? value : [value];
      // Remove any values that are not useful for filtering, e.g. null/boolean/undefined.
      valueArray.filter((filterValue) => Boolean(filterValue));
      // Ignore this section if there are no useful values to filter by:
      if (valueArray.length === 0) {
        return;
      }
      // If this section does not already exist then create a new map to store
      // the values and counts.
      let storedFilter = filters.get(filter);
      if (!storedFilter) {
        const filterValues: FilterValues = new Map();
        filters.set(filter, filterValues);
        storedFilter = filters.get(filter);
      }
      valueArray.forEach((filterValue) => {
        if (storedFilter) {
          const storedValue = storedFilter.get(filterValue) || 0;
          storedFilter.set(filterValue, storedValue + 1);
        }
      });
    });
  });
  return filters;
};

const sortByFilterKey = (
  a: [FilterValue, number],
  b: [FilterValue, number]
) => {
  const aValue = a[0];
  const bValue = b[0];
  if (aValue < bValue) {
    return -1;
  }
  if (aValue > bValue) {
    return 1;
  }
  return 0;
};

const FilterAccordion = <I, PK extends keyof I>({
  "aria-label": ariaLabel,
  disabled,
  filterNames,
  filterOrder,
  filtersToString,
  filterString,
  getCurrentFilters,
  getValue,
  getValueDisplay,
  isFilterActive,
  items,
  onUpdateFilterString,
  toggleFilter,
}: Props<I, PK>): React.ReactElement => {
  const currentFilters = getCurrentFilters(filterString);
  const [expandedSection, setExpandedSection] = useState<string>();
  const sections = useMemo(() => {
    const filterOptions = getFilters<I, PK>(items, filterOrder, getValue);
    return filterOrder.reduce<Section[]>((options, filter) => {
      const filterValues = filterOptions.get(filter);
      if (filterValues && filterValues.size > 0) {
        options.push({
          title: filterNames.get(filter),
          content: (
            <List
              className="u-no-margin--bottom"
              items={Array.from(filterValues)
                .sort(sortByFilterKey)
                .map(([filterValue, count]) => {
                  const isActive = isFilterActive(
                    currentFilters,
                    filter,
                    filterValue,
                    true
                  );
                  return (
                    <Button
                      appearance="base"
                      aria-checked={isActive}
                      className={classNames(
                        "u-align-text--left u-no-margin--bottom filter-accordion__item is-dense",
                        {
                          "is-active": isActive,
                        }
                      )}
                      data-testid={`filter-${filter}`}
                      onClick={() => {
                        const newFilters = toggleFilter(
                          currentFilters,
                          filter,
                          filterValue,
                          true
                        );
                        onUpdateFilterString(filtersToString(newFilters));
                      }}
                      role="checkbox"
                    >
                      {getValueDisplay
                        ? getValueDisplay(filter, filterValue)
                        : filterValue}{" "}
                      ({count})
                    </Button>
                  );
                })}
            />
          ),
          key: filter,
        });
      }
      return options;
    }, []);
  }, [
    currentFilters,
    filterNames,
    filterOrder,
    filtersToString,
    getValue,
    getValueDisplay,
    isFilterActive,
    items,
    onUpdateFilterString,
    toggleFilter,
  ]);

  return (
    <ContextualMenu
      aria-label={ariaLabel}
      className="filter-accordion filter-accordion--expanded"
      constrainPanelWidth
      hasToggleIcon
      position="left"
      toggleClassName="filter-accordion__toggle"
      toggleDisabled={disabled || items?.length === 0}
      toggleLabel={Labels.Toggle}
    >
      <Accordion
        className="filter-accordion__dropdown"
        expanded={expandedSection}
        externallyControlled
        onExpandedChange={(id, _title) => {
          setExpandedSection(id);
        }}
        sections={sections}
      />
    </ContextualMenu>
  );
};

export default FilterAccordion;
