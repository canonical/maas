import { getDiscoveryValue } from "./search";

import * as factory from "@/testing/factories";

describe("search", () => {
  describe("getDiscoveryValue", () => {
    it("can get an attribute directly from the discovery", () => {
      const discovery = factory.discovery({ id: 808 });
      expect(getDiscoveryValue(discovery, "id")).toBe(808);
    });
  });
});
