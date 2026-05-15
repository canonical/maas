import { parseNumberId } from "./parseNumberId";

describe("parseNumberId", () => {
  it("handles a number", () => {
    expect(parseNumberId(1)).toBe(1);
  });

  it("handles a string", () => {
    expect(parseNumberId("1")).toBe(1);
  });

  it("handles an empty string", () => {
    expect(parseNumberId("")).toBeNull();
  });

  it("handles non-number strings", () => {
    expect(parseNumberId("nope")).toBeNull();
  });
});
