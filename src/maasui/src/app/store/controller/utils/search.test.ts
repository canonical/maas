import { FilterControllers, getControllerValue } from "./search";

import type { Filters } from "@/app/utils/search/filter-handlers";
import * as factory from "@/testing/factories";

describe("search", () => {
  describe("getControllerValue", () => {
    it("can get an attribute via a mapping function", () => {
      const controller = factory.controller({
        domain: { id: 1, name: "danger" },
      });
      expect(getControllerValue(controller, "domain")).toBe("danger");
    });

    it("can get an attribute directly from the controller", () => {
      const controller = factory.controller({ hostname: "miami-controller" });
      expect(getControllerValue(controller, "hostname")).toBe(
        "miami-controller"
      );
    });

    it("can get an attribute that is an array directly from the controller", () => {
      const controller = factory.controller({ permissions: ["edit", "read"] });
      expect(getControllerValue(controller, "permissions")).toStrictEqual([
        "edit",
        "read",
      ]);
    });

    it("can get tags", () => {
      const tags = [
        factory.tag({ id: 1, name: "tag1" }),
        factory.tag({ id: 2, name: "tag2" }),
        factory.tag({ id: 3, name: "tag3" }),
      ];
      const controller = factory.controller({ tags: [1, 2] });
      expect(getControllerValue(controller, "tags", { tags })).toStrictEqual([
        "tag1",
        "tag2",
      ]);
    });
  });

  describe("FilterController", () => {
    const scenarios: {
      filters: Filters;
      input: string;
      output?: string;
    }[] = [
      {
        input: "free-text",
        filters: {
          q: ["free-text"],
        },
      },
      {
        input: "hostname:(miami)",
        filters: {
          q: [],
          hostname: ["miami"],
        },
      },
      {
        input: "tags:(tag1,tag2)",
        filters: {
          q: [],
          tags: ["tag1", "tag2"],
        },
      },
      {
        input: "free-text hostname:(miami) tags:(tag1,tag2)",
        filters: {
          q: ["free-text"],
          hostname: ["miami"],
          tags: ["tag1", "tag2"],
        },
      },
    ];

    scenarios.forEach((scenario) => {
      describe("input:" + scenario.input, () => {
        it("getCurrentFilters", () => {
          expect(FilterControllers.getCurrentFilters(scenario.input)).toEqual(
            scenario.filters
          );
        });
      });
    });
  });
});
