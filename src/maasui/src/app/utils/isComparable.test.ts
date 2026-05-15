import { isComparable } from "./isComparable";

describe("isComparable", () => {
  it("handles comparable values", () => {
    expect(isComparable("value")).toBe(true);
    expect(isComparable(1)).toBe(true);
    expect(isComparable(-1)).toBe(true);
  });

  it("handles incomparable values", () => {
    expect(isComparable([])).toBe(false);
    expect(isComparable({})).toBe(false);
    expect(isComparable(null)).toBe(false);
    expect(isComparable(true)).toBe(false);
    expect(isComparable(false)).toBe(false);
  });
});
