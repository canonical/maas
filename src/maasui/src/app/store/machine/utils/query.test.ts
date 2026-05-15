import { FetchGroupKey } from "../types/actions";

import { mapSortDirection } from "./common";
import {
  timeUntilStale,
  transformToFetchParams,
  generateCallId,
} from "./query";

import type { Sort } from "@/app/base/types";

describe("machine utilities", () => {
  beforeEach(() => {
    vi.spyOn(Date, "now").mockImplementation(() => 1000);
  });

  afterEach(() => {
    vi.spyOn(Date, "now").mockRestore();
  });

  describe("timeUntilStale", () => {
    it("should return the remaining time until stale", () => {
      expect(timeUntilStale(500, 1000)).toBe(500);
    });

    it("should return 0 if the time is already stale", () => {
      expect(timeUntilStale(500)).toBe(0);
    });
  });

  describe("transformToFetchParams", () => {
    const options = {
      filters: {},
      collapsedGroups: [],
      grouping: FetchGroupKey.Status,
      pagination: {
        currentPage: 1,
        pageSize: 10,
        setCurrentPage: vi.fn(),
      },
      sortDirection: "asc" as Sort["direction"],
      sortKey: FetchGroupKey.Status,
    };

    it("should return the correct fetch parameters when options are provided", () => {
      expect(transformToFetchParams(options)).toEqual({
        filter: {},
        group_collapsed: [],
        group_key: "status",
        page_number: 1,
        page_size: 10,
        sort_direction: mapSortDirection(options.sortDirection),
        sort_key: "status",
      });
    });

    it("should return null when no options are provided", () => {
      expect(transformToFetchParams()).toBe(null);
    });
  });

  describe("generateCallId", () => {
    it("should return a sorted, stringified version of the parameters when options are provided", () => {
      const options = { b: 1, a: 2, c: { e: 3, d: 4 } };
      expect(generateCallId(options)).toBe('{"a":2,"b":1,"c":{"d":4,"e":3}}');
    });

    it('should return "{}" when no options are provided', () => {
      expect(generateCallId()).toBe("{}");
    });
  });
});
