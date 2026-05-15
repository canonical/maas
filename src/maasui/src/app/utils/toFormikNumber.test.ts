import { toFormikNumber } from "./toFormikNumber";

describe("toFormikNumber", () => {
  it("handles a number", () => {
    expect(toFormikNumber(1)).toBe(1);
  });

  it("handles a string", () => {
    expect(toFormikNumber("1")).toBe(1);
  });

  it("handles an empty string", () => {
    expect(toFormikNumber("")).toBeUndefined();
  });
});
