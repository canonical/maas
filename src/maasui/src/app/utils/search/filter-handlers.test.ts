import FilterHandlers from "./filter-handlers";
import type { Filters } from "./filter-handlers";

describe("FilterHandlers", () => {
  let TestHandlers: FilterHandlers;
  const scenarios: {
    filters: Filters;
    input: string;
    output?: string;
  }[] = [
    {
      input: "",
      filters: {
        q: [],
      },
    },
    {
      input: "moon",
      filters: {
        q: ["moon"],
      },
    },
    {
      input: "1moon",
      filters: {
        q: ["1moon"],
      },
    },
    {
      input: "m",
      filters: {
        q: ["m"],
      },
    },
    {
      input: "moon !sun",
      filters: {
        q: ["moon", "!sun"],
      },
    },
    {
      input: "moon !!sun",
      filters: {
        q: ["moon", "!!sun"],
      },
    },
    {
      input: "moon status:(new)",
      filters: {
        q: ["moon"],
        status: ["new"],
      },
    },
    {
      input: "moon status:(1new)",
      filters: {
        q: ["moon"],
        status: ["1new"],
      },
    },
    {
      input: "moon status:(new) star",
      output: "moon star status:(new)",
      filters: {
        q: ["moon", "star"],
        status: ["new"],
      },
    },
    {
      input: "moon status:(new,deployed)",
      filters: {
        q: ["moon"],
        status: ["new", "deployed"],
      },
    },
    {
      input: "moon status:(new,failed disk erasing)",
      filters: {
        q: ["moon"],
        status: ["new", "failed disk erasing"],
      },
    },
    {
      input: "moon status:!(!new,failed disk erasing)",
      output: "moon status:(!!new,!failed disk erasing)",
      filters: {
        q: ["moon"],
        status: ["!!new", "!failed disk erasing"],
      },
    },
    {
      input: "moon status:!!(new,failed commissioning)",
      output: "moon status:(new,failed commissioning)",
      filters: {
        q: ["moon"],
        status: ["new", "failed commissioning"],
      },
    },
    {
      input: "moon status:!!(!new)",
      output: "moon status:(!new)",
      filters: {
        q: ["moon"],
        status: ["!new"],
      },
    },
    {
      input: "moon status:!!(!!new)",
      output: "moon status:(!!new)",
      filters: {
        q: ["moon"],
        status: ["!!new"],
      },
    },
    {
      input: "moon status:(new,failed disk erasing,pending)",
      filters: {
        q: ["moon"],
        status: ["new", "failed disk erasing", "pending"],
      },
    },
    {
      input: "moon status:new,deployed",
      output: "moon status:(new,deployed)",
      filters: {
        q: ["moon"],
        status: ["new", "deployed"],
      },
    },
    {
      input: "moon status:new,failed disk erasing",
      output: "moon disk erasing status:(new,failed)",
      filters: {
        q: ["moon", "disk", "erasing"],
        status: ["new", "failed"],
      },
    },
    {
      input: "moon status:(new,failed disk erasing",
      output: "moon disk erasing",
      filters: {
        q: ["moon", "disk", "erasing"],
      },
    },
    {
      input: "moon status:(",
      output: "moon",
      filters: {
        q: ["moon"],
      },
    },
    {
      input: "moon status:",
      output: "moon",
      filters: {
        q: ["moon"],
      },
    },
    {
      input: "moon mac:28:76:03:77:5a:b5 status:new",
      output: "moon mac:(28:76:03:77:5a:b5) status:(new)",
      filters: {
        q: ["moon"],
        mac: ["28:76:03:77:5a:b5"],
        status: ["new"],
      },
    },
    {
      input: "moon mac:(28:76:03:77:5a:b5) status:new",
      output: "moon mac:(28:76:03:77:5a:b5) status:(new)",
      filters: {
        q: ["moon"],
        mac: ["28:76:03:77:5a:b5"],
        status: ["new"],
      },
    },
    {
      input: "moon mac:(28:76:03:77:5a:b5,d6:4d:bc:0e:26:bc)",
      output: "moon mac:(28:76:03:77:5a:b5,d6:4d:bc:0e:26:bc)",
      filters: {
        q: ["moon"],
        mac: ["28:76:03:77:5a:b5", "d6:4d:bc:0e:26:bc"],
      },
    },
    {
      input: "moon status:(=new,!failed disk erasing,=!pending,!=deploying)",
      filters: {
        q: ["moon"],
        status: ["=new", "!failed disk erasing", "=!pending", "!=deploying"],
      },
    },
    {
      input: "koala-type:()",
      filters: {
        q: [],
        "koala-type": [""],
      },
    },
    {
      input: "koala-type",
      filters: {
        q: [],
        "koala-type": [""],
      },
    },
    {
      input: "koala-type:(qwerty)",
      filters: {
        q: [],
        "koala-type": ["qwerty"],
      },
    },
    {
      input: "koala-type:(=qwerty,!dvorak)",
      filters: {
        q: [],
        "koala-type": ["=qwerty", "!dvorak"],
      },
    },
    {
      input: "free-text koala-type:(qwerty) koala-service:(dvorak)",
      filters: {
        q: ["free-text"],
        "koala-type": ["qwerty"],
        "koala-service": ["dvorak"],
      },
    },
    {
      input: "koala-type:(query with spaces)",
      filters: {
        q: [],
        "koala-type": ["query with spaces"],
      },
    },
  ];

  beforeEach(() => {
    TestHandlers = new FilterHandlers([
      { filter: "koala_filter", prefix: "koala" },
    ]);
  });

  scenarios.forEach((scenario) => {
    describe("input:" + scenario.input, () => {
      it("getCurrentFilters", () => {
        expect(TestHandlers.getCurrentFilters(scenario.input)).toEqual(
          scenario.filters
        );
      });

      it("filtersToString", () => {
        // Skip the ones with filters equal to null.
        if (scenario.filters) {
          return;
        }

        expect(TestHandlers.filtersToString(scenario.filters)).toEqual(
          scenario.output || scenario.input
        );
      });
    });
  });

  describe("isFilterActive", () => {
    it("returns false if type not in filter", () => {
      expect(TestHandlers.isFilterActive({}, "type", "invalid")).toBe(false);
    });

    it("returns false if there are no filters", () => {
      expect(TestHandlers.isFilterActive(null, "type", "invalid")).toBe(false);
    });

    it("returns false if value not in type", () => {
      expect(
        TestHandlers.isFilterActive(
          {
            type: ["not"],
          },
          "type",
          "invalid"
        )
      ).toBe(false);
    });

    it("returns true if value in type", () => {
      expect(
        TestHandlers.isFilterActive(
          {
            type: ["valid"],
          },
          "type",
          "valid"
        )
      ).toBe(true);
    });

    it("returns false if exact value not in type", () => {
      expect(
        TestHandlers.isFilterActive(
          {
            type: ["valid"],
          },
          "type",
          "valid",
          true
        )
      ).toBe(false);
    });

    it("returns true if exact value in type", () => {
      expect(
        TestHandlers.isFilterActive(
          {
            type: ["=valid"],
          },
          "type",
          "valid",
          true
        )
      ).toBe(true);
    });

    it("returns true if lowercase value in type", () => {
      expect(
        TestHandlers.isFilterActive(
          {
            type: ["=Valid"],
          },
          "type",
          "valid",
          true
        )
      ).toBe(true);
    });

    it("returns true if a prefixed filter key exists in filter list", () => {
      expect(
        TestHandlers.isFilterActive(
          {
            "koala-type": ["production"],
          },
          "koala_filter",
          "type"
        )
      ).toBe(true);
    });
  });

  describe("toggleFilter", () => {
    it("adds type to filters", () => {
      expect(TestHandlers.toggleFilter({}, "type", "value")).toEqual({
        type: ["value"],
      });
    });

    it("adds value to type in filters", () => {
      const filters = {
        type: ["exists"],
      };
      expect(TestHandlers.toggleFilter(filters, "type", "value")).toEqual({
        type: ["exists", "value"],
      });
    });

    it("removes value from type in filters", () => {
      const filters = {
        type: ["exists", "value"],
      };
      expect(TestHandlers.toggleFilter(filters, "type", "value")).toEqual({
        type: ["exists"],
      });
    });

    it("adds exact value to type in filters", () => {
      const filters = {
        type: ["exists"],
      };
      expect(TestHandlers.toggleFilter(filters, "type", "value", true)).toEqual(
        {
          type: ["exists", "=value"],
        }
      );
    });

    it("removes exact value from type in filters", () => {
      const filters = {
        type: ["exists", "value", "=value"],
      };
      expect(TestHandlers.toggleFilter(filters, "type", "value", true)).toEqual(
        {
          type: ["exists", "value"],
        }
      );
    });

    it("removes lowercase value from type in filters", () => {
      const filters = {
        type: ["exists", "=Value"],
      };
      expect(TestHandlers.toggleFilter(filters, "type", "value", true)).toEqual(
        {
          type: ["exists"],
        }
      );
    });

    it("can handle an expected value when it already exists", () => {
      const filters = {
        type: ["value"],
      };
      expect(
        TestHandlers.toggleFilter(filters, "type", "value", false, true)
      ).toEqual({
        type: ["value"],
      });
    });

    it("can toggle an expected value", () => {
      const filters = {
        type: ["value"],
      };
      expect(
        TestHandlers.toggleFilter(filters, "type", "value", false, false)
      ).toEqual({});
    });

    it("can handle an expected false value when it already does not exist", () => {
      expect(
        TestHandlers.toggleFilter({}, "type", "value", false, false)
      ).toEqual({});
    });

    it("can toggle an expected false value", () => {
      expect(
        TestHandlers.toggleFilter({}, "type", "value", false, true)
      ).toEqual({
        type: ["value"],
      });
    });

    it("can add a prefixed filter that doesn't currently exist", () => {
      expect(
        TestHandlers.toggleFilter({}, "koala_filter", "koala-value")
      ).toEqual({
        "koala-value": [""],
      });
    });

    it("can remove a prefixed filter that currently exists", () => {
      const filters = {
        "koala-value": [""],
      };
      expect(
        TestHandlers.toggleFilter(filters, "koala_filter", "koala-value")
      ).toEqual({});
    });

    it("can remove a prefixed filter that currently exists with a value", () => {
      const filters = {
        "koala-value": ["cuddly"],
      };
      expect(
        TestHandlers.toggleFilter(filters, "koala_filter", "koala-value")
      ).toEqual({});
    });

    it("handles an expected prefixed filter that currently exists", () => {
      const filters = {
        "koala-value": [""],
      };
      expect(
        TestHandlers.toggleFilter(
          filters,
          "koala_filter",
          "koala-value",
          false,
          true
        )
      ).toEqual({
        "koala-value": [""],
      });
    });

    it("handles a not expected prefixed filter that does not currently exist", () => {
      expect(
        TestHandlers.toggleFilter(
          {},
          "koala_filter",
          "koala-value",
          false,
          false
        )
      ).toEqual({});
    });

    it("can toggle a prefixed filter that is provided without the prefix", () => {
      expect(TestHandlers.toggleFilter({}, "koala_filter", "value")).toEqual({
        "koala-value": [""],
      });
    });
  });

  describe("getEmptyFilter", () => {
    it("includes q empty list", () => {
      expect(TestHandlers.getEmptyFilter()).toEqual({ q: [] });
    });

    it("returns different object on each call", () => {
      const one = TestHandlers.getEmptyFilter();
      const two = TestHandlers.getEmptyFilter();
      expect(one).not.toBe(two);
    });
  });

  describe("queryStringToFilters", () => {
    it("can convert a query string to a filter object", () => {
      expect(
        TestHandlers.queryStringToFilters(
          "?q=moon%2Csun&status=new,failed+comissioning&zone=!south&hostname="
        )
      ).toEqual({
        q: ["moon", "sun"],
        status: ["new", "failed comissioning"],
        zone: ["!south"],
      });
    });

    it("can convert a query string to a filter object and back", () => {
      const queryString =
        "?q=moon%2Csun&status=new%2Cfailed+comissioning&zone=%21south";
      const queryObject = TestHandlers.queryStringToFilters(queryString);
      expect(TestHandlers.filtersToQueryString(queryObject)).toEqual(
        queryString
      );
    });
  });

  describe("filtersToQueryString", () => {
    it("can convert a filter object to a query string", () => {
      expect(
        TestHandlers.filtersToQueryString({
          q: ["moon", "sun"],
          hostname: [],
          status: ["new", "failed comissioning"],
          zone: ["!south"],
        })
      ).toEqual("?q=moon%2Csun&status=new%2Cfailed+comissioning&zone=%21south");
    });

    it("does not include selected filters in query string", () => {
      expect(
        TestHandlers.filtersToQueryString({
          q: ["moon", "sun"],
          in: ["selected"],
        })
      ).toEqual("?q=moon%2Csun");
    });

    it("can convert a filter object to a query string and back", () => {
      const queryObject = {
        q: ["moon", "sun"],
        status: ["new", "failed comissioning"],
        zone: ["!south"],
      };
      const queryString = TestHandlers.filtersToQueryString(queryObject);
      expect(TestHandlers.queryStringToFilters(queryString)).toEqual(
        queryObject
      );
    });
  });
});
