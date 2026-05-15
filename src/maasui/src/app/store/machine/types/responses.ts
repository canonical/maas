import type { FilterGroup, Machine, MachineStateListGroup } from "./base";

export type FilterGroupResponse = Omit<FilterGroup, "options">;

export type FetchResponseGroup = Omit<MachineStateListGroup, "items"> & {
  items: Machine[];
};

export type FetchResponse = {
  count: number;
  cur_page: number;
  num_pages: number;
  groups: FetchResponseGroup[];
};
