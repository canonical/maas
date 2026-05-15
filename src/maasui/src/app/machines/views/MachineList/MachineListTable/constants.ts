import { SortDirection } from "@/app/base/types";
import { FetchGroupKey } from "@/app/store/machine/types";
export const DEFAULTS = {
  pageSize: 50,
  sortDirection: SortDirection.ASCENDING,
  // TODO: change this to fqdn when the API supports it:
  // https://github.com/canonical/app-tribe/issues/1268
  sortKey: FetchGroupKey.Hostname,
  grouping: FetchGroupKey.Status,
};
