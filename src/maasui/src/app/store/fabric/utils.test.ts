import { getFabricDisplay } from "./utils";

import * as factory from "@/testing/factories";

describe("fabric utils", () => {
  describe("getFabricDisplay", function () {
    it("returns undefined if no object is passed in", function () {
      expect(getFabricDisplay(null)).toBe(null);
    });

    it("returns name if name exists", function () {
      const fabric = factory.fabric({ name: "fabric-name" });
      expect(getFabricDisplay(fabric)).toBe("fabric-name");
    });

    it("returns name if name is null", function () {
      const fabric = factory.fabric({ id: 99, name: "" });
      expect(getFabricDisplay(fabric)).toBe("fabric-99");
    });
  });
});
