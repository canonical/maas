import { hasMetadata } from "./readScript";

describe("readScript", () => {
  describe("hasMetadata", () => {
    it("returns true if a file has a metadata header", () => {
      const contents = "# --- Start MAAS 1.0 script metadata ---\n";

      expect(hasMetadata(contents)).toEqual(true);
    });

    it("returns false if a file has no metadata header", () => {
      const contents = "#!bin/sh\necho 'foo'\n";

      expect(hasMetadata(contents)).toEqual(false);
    });
  });
});
