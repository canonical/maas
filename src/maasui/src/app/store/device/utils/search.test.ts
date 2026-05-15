import { FilterDevices, getDeviceValue } from "./search";

import type { Filters } from "@/app/utils/search/filter-handlers";
import * as factory from "@/testing/factories";

describe("search", () => {
  describe("getDeviceValue", () => {
    it("can get an attribute via a mapping function", () => {
      const device = factory.device({ zone: { id: 1, name: "danger" } });
      expect(getDeviceValue(device, "zone")).toBe("danger");
    });

    it("can get an attribute directly from the device", () => {
      const device = factory.device({ hostname: "miami-device" });
      expect(getDeviceValue(device, "hostname")).toBe("miami-device");
    });

    it("can get an attribute that is an array directly from the device", () => {
      const device = factory.device({ fabrics: ["fabric-0", "fabric-1"] });
      expect(getDeviceValue(device, "fabrics")).toStrictEqual([
        "fabric-0",
        "fabric-1",
      ]);
    });

    it("can get tags", () => {
      const tags = [
        factory.tag({ id: 1, name: "tag1" }),
        factory.tag({ id: 2, name: "tag2" }),
        factory.tag({ id: 3, name: "tag3" }),
      ];
      const device = factory.device({ tags: [1, 2] });
      expect(getDeviceValue(device, "tags", { tags })).toStrictEqual([
        "tag1",
        "tag2",
      ]);
    });
  });

  describe("FilterDevice", () => {
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
          expect(FilterDevices.getCurrentFilters(scenario.input)).toEqual(
            scenario.filters
          );
        });
      });
    });
  });
});
