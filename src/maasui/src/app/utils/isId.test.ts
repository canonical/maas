import { isId } from "./isId";

describe("isId", () => {
  it("handles a number", () => {
    expect(isId(1)).toBe(true);
  });
  it("handles zero", () => {
    expect(isId(0)).toBe(true);
  });

  it("handles a string", () => {
    expect(isId("abc123")).toBe(true);
  });

  it("handles an empty string", () => {
    expect(isId("")).toBe(false);
  });

  it("handles null", () => {
    expect(isId(null)).toBe(false);
  });

  it("handles undefined", () => {
    expect(isId()).toBe(false);
  });
});
