import { getTagNamesForIds, getTagsDisplay } from "./utils";

import * as factory from "@/testing/factories";

describe("tag utils", () => {
  describe("getTagsDisplay", () => {
    it("can get tags for display", () => {
      const tags = [
        factory.tag({ name: "tag1" }),
        factory.tag({ name: "tag2" }),
      ];
      expect(getTagsDisplay(tags)).toBe("tag1, tag2");
    });

    it("handles no tags", () => {
      expect(getTagsDisplay([])).toBe("-");
    });
  });

  describe("getTagNamesForIds", () => {
    it("can map tag ids to names", () => {
      const tags = [
        factory.tag({ id: 1, name: "tag1" }),
        factory.tag({ id: 2, name: "tag2" }),
        factory.tag({ id: 3, name: "tag3" }),
      ];
      expect(getTagNamesForIds([1, 3], tags)).toStrictEqual(["tag1", "tag3"]);
    });
  });
});
