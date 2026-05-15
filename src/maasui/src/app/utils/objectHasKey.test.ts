import { objectHasKey } from "./objectHasKey";

describe("objectHasKey", () => {
  it("handles a string that is a valid key", () => {
    expect(objectHasKey("validKey", { validKey: "yep" })).toBe(true);
  });

  it("handles a string that is an invalid key", () => {
    expect(objectHasKey("invalidKey" as string, { validKey: "nope" })).toBe(
      false
    );
  });
});
