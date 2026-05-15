import type { PublicConfigName } from "../apiclient";

import { getConfigsFromResponse, simpleObjectEquality } from "./utils";

describe("settings utils", () => {
  describe("simpleObjectEquality", () => {
    it("returns true if two objects have the same key value pairs in the same order", () => {
      const obj1 = { key1: "value1", key2: "value2" };
      const obj2 = { key1: "value1", key2: "value2" };
      expect(simpleObjectEquality(obj1, obj2)).toBe(true);
    });
  });
  describe("getConfigsFromResponse", () => {
    it("returns an object with the specified configuration names and their values", () => {
      const items = [
        { name: "config1", value: "value1" },
        { name: "config2", value: "value2" },
        { name: "config3", value: "value3" },
      ];
      const names = ["config1", "config3"];
      const result = getConfigsFromResponse(items, names as PublicConfigName[]);
      expect(result).toEqual({
        config1: "value1",
        config3: "value3",
      });
    });

    it("returns an empty object if no matching configurations are found", () => {
      const items = [{ name: "config1", value: "value1" }];
      const names = ["config2"];
      const result = getConfigsFromResponse(items, names as PublicConfigName[]);
      expect(result).toEqual({});
    });
  });
});
