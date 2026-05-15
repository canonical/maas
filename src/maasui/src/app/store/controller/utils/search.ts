import type { Controller } from "@/app/store/controller/types";
import { ControllerMeta } from "@/app/store/controller/types";
import type { Tag } from "@/app/store/tag/types";
import { getTagNamesForIds } from "@/app/store/tag/utils";
import type { FilterValue } from "@/app/utils/search/filter-handlers";
import {
  isFilterValue,
  isFilterValueArray,
} from "@/app/utils/search/filter-handlers";
import FilterItems from "@/app/utils/search/filter-items";

type ExtraData = {
  tags: Tag[];
};

type SearchMappings = Record<
  string,
  (
    controller: Controller,
    extraData?: ExtraData
  ) => FilterValue | FilterValue[] | null
>;

// Helpers that convert the pseudo field on the controller to an actual value.
const searchMappings: SearchMappings = {
  domain: (controller: Controller) => controller.domain.name,
  tags: (controller, extraData) =>
    extraData?.tags ? getTagNamesForIds(controller.tags, extraData.tags) : [],
};

export const getControllerValue = (
  controller: Controller,
  filter: string,
  extraData?: ExtraData
): FilterValue | FilterValue[] | null => {
  const mapFunc = filter in searchMappings ? searchMappings[filter] : null;
  let value: FilterValue | FilterValue[] | null = null;
  if (mapFunc) {
    value = mapFunc(controller, extraData);
  } else if (controller.hasOwnProperty(filter)) {
    const controllerValue = controller[filter as keyof Controller];
    // Only return values that are valid for filters, all other values should
    // use the map function above.
    if (isFilterValue(controllerValue) || isFilterValueArray(controllerValue)) {
      value = controllerValue;
    }
  }
  return value;
};

export const FilterControllers = new FilterItems<
  Controller,
  ControllerMeta.PK,
  ExtraData
>(ControllerMeta.PK, getControllerValue);
