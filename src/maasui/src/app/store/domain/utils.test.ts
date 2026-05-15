import { isDomainDetails } from "./utils";

import * as factory from "@/testing/factories";

describe("domain utils", () => {
  describe("isDomainDetails", () => {
    it("identifies domain details", () => {
      expect(isDomainDetails(factory.domainDetails())).toBe(true);
    });

    it("handles a base domain", () => {
      expect(isDomainDetails(factory.domain())).toBe(false);
    });

    it("handles no domain", () => {
      expect(isDomainDetails()).toBe(false);
    });

    it("handles null", () => {
      expect(isDomainDetails(null)).toBe(false);
    });
  });
});
